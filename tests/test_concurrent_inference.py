from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
from threading import Barrier, Lock

from PIL import Image

from sunsetscore.inference import runner
from sunsetscore.inference.runner import LocalVisionScorer
from sunsetscore.runtime import RuntimeEnvironment


def _environment(tmp_path: Path, backend: str) -> RuntimeEnvironment:
    return RuntimeEnvironment(
        executable=tmp_path / backend / "llama-mtmd-cli.exe",
        model=tmp_path / "model.gguf",
        projector=tmp_path / "mmproj.gguf",
        version="fake-model",
        backend=backend,
        device=f"Fake {backend}",
        total_gpu_memory_mib=16_000 if backend == "cuda" else None,
        free_gpu_memory_mib=15_000 if backend == "cuda" else None,
    )


def _image(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    Image.new("RGB", (32, 24), "orange").save(path)
    return path


def test_concurrent_gpu_failures_trigger_one_cpu_fallback(
    tmp_path, monkeypatch
) -> None:
    gpu_barrier = Barrier(2)
    count_lock = Lock()
    fallback_count = 0
    cpu = _environment(tmp_path, "cpu")

    def fake_run(command, **kwargs):
        if "cuda" in command[0]:
            gpu_barrier.wait(timeout=5)
            return subprocess.CompletedProcess(
                command, 1, stdout="", stderr="GPU failed"
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"score":55,"reason":"CPU fallback"}',
            stderr="",
        )

    def fake_environment(*, force_cpu):
        nonlocal fallback_count
        assert force_cpu
        with count_lock:
            fallback_count += 1
        return cpu

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(runner, "ensure_runtime_environment", fake_environment)
    scorer = LocalVisionScorer(_environment(tmp_path, "cuda"))
    images = [_image(tmp_path, "one.jpg"), _image(tmp_path, "two.jpg")]

    with ThreadPoolExecutor(max_workers=2) as pool:
        scores = list(pool.map(scorer.score, images))

    assert [item.score for item in scores] == [55, 55]
    assert fallback_count == 1
    assert scorer.inference_backend == "cpu"
