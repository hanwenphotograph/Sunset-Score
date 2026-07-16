from __future__ import annotations

from pathlib import Path
import subprocess

from PIL import Image
import pytest

from sunsetscore.errors import InferenceError
from sunsetscore.inference.parser import parse_model_response
from sunsetscore.inference import runner
from sunsetscore.inference.runner import LocalVisionScorer
from sunsetscore.runtime import RuntimeEnvironment


def _environment(tmp_path: Path, *, backend: str = "cpu") -> RuntimeEnvironment:
    return RuntimeEnvironment(
        executable=tmp_path / "llama-mtmd-cli",
        model=tmp_path / "model.gguf",
        projector=tmp_path / "mmproj.gguf",
        version="fake-model",
        backend=backend,
        device="Fake GPU" if backend != "cpu" else "Fake CPU",
    )


def _image(tmp_path: Path) -> Path:
    path = tmp_path / "photo.jpg"
    Image.new("RGB", (32, 24), "orange").save(path)
    return path


def test_parser_uses_last_valid_json_object() -> None:
    output = 'noise {"score": 2} more {"score":87,"reason":"  红色 云层  "}'

    result = parse_model_response(output)

    assert result.score == 87
    assert result.reason == "红色 云层"


@pytest.mark.parametrize(
    "output",
    [
        "no json",
        '{"score": true, "reason": "x"}',
        '{"score": 101, "reason": "x"}',
        '{"score": 20, "reason": ""}',
    ],
)
def test_parser_rejects_invalid_responses(output: str) -> None:
    with pytest.raises(InferenceError):
        parse_model_response(output)


def test_runner_builds_constrained_deterministic_command(tmp_path, monkeypatch) -> None:
    captured: list[str] = []

    def fake_run(command, **kwargs):
        captured.extend(command)
        image_path = Path(command[command.index("--image") + 1])
        assert image_path.exists()
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"score":76,"reason":"天空存在橙红色云层"}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    scorer = LocalVisionScorer(_environment(tmp_path))

    result = scorer.score(_image(tmp_path))

    assert result.score == 76
    assert "--json-schema" in captured
    assert captured[captured.index("--temp") + 1] == "0"
    assert captured[captured.index("--seed") + 1] == "0"
    assert captured[captured.index("--image-max-tokens") + 1] == "1280"
    assert captured[captured.index("--log-verbosity") + 1] == "0"
    assert captured[captured.index("--device") + 1] == "none"
    assert captured[captured.index("--gpu-layers") + 1] == "0"
    assert "--log-disable" not in captured


def test_gpu_runner_uses_automatic_layer_offload(tmp_path, monkeypatch) -> None:
    captured: list[str] = []

    def fake_run(command, **kwargs):
        captured.extend(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"score":80,"reason":"明显晚霞"}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    LocalVisionScorer(_environment(tmp_path, backend="cuda")).score(_image(tmp_path))

    assert captured[captured.index("--gpu-layers") + 1] == "auto"
    assert captured[captured.index("--fit") + 1] == "on"
    assert "--device" not in captured


def test_gpu_inference_failure_falls_back_to_cpu(tmp_path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_run(command, **kwargs):
        calls.append(command[0])
        if len(calls) == 1:
            return subprocess.CompletedProcess(
                command, 1, stdout="", stderr="GPU failed"
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"score":55,"reason":"CPU fallback"}',
            stderr="",
        )

    cpu = _environment(tmp_path / "cpu", backend="cpu")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        runner,
        "ensure_runtime_environment",
        lambda *, force_cpu: cpu if force_cpu else pytest.fail("must force CPU"),
    )
    scorer = LocalVisionScorer(_environment(tmp_path / "gpu", backend="cuda"))

    result = scorer.score(_image(tmp_path))

    assert result.score == 55
    assert len(calls) == 2
    assert scorer.inference_backend == "cpu"


def test_runner_retries_once_when_json_is_invalid(tmp_path, monkeypatch) -> None:
    outputs = iter(["invalid", '{"score":30,"reason":"证据较弱"}'])
    calls = 0

    def fake_run(command, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(command, 0, stdout=next(outputs), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = LocalVisionScorer(_environment(tmp_path)).score(_image(tmp_path))

    assert calls == 2
    assert result.score == 30


def test_runner_reports_nonzero_exit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            7,
            stdout="",
            stderr="model failed",
        ),
    )

    with pytest.raises(InferenceError, match="退出码为 7.*model failed"):
        LocalVisionScorer(_environment(tmp_path)).score(_image(tmp_path))
