from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from PIL import Image
import pytest

from sunsetscore.errors import InferenceError
from sunsetscore.inference import runner
from sunsetscore.inference.parser import parse_model_response
from sunsetscore.inference.prompt import CATEGORY_SCORES, SCORING_PROMPT
from sunsetscore.inference.runner import LocalVisionScorer
from sunsetscore.runtime import RuntimeEnvironment


def _environment(tmp_path: Path, *, backend: str = "cpu") -> RuntimeEnvironment:
    executable = tmp_path / "llama-mtmd-cli.exe"
    return RuntimeEnvironment(
        executable=executable,
        server_executable=executable.with_name("llama-server.exe"),
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


def _fake_server(monkeypatch, outputs: Iterator[str | Exception]):
    instances = []

    class FakeServer:
        def __init__(self, environment, *, slots):
            self.environment = environment
            self.slots = slots
            self.closed = False
            self.calls = 0
            instances.append(self)

        def complete(self, image, prompt):
            self.calls += 1
            assert image.exists()
            assert prompt.startswith(SCORING_PROMPT)
            value = next(outputs)
            if isinstance(value, Exception):
                raise value
            return value

        def close(self):
            self.closed = True

    monkeypatch.setattr(runner, "LlamaServer", FakeServer)
    return instances


def test_prompt_requires_visibly_colored_clouds_for_high_scores() -> None:
    assert "评分目标不是日落本身" in SCORING_PROMPT
    assert "没有可辨认的自然云层时只能选择" in SCORING_PROMPT
    assert "云体没有明确的红、橙、粉、金或霞光紫色时不能选择" in SCORING_PROMPT
    assert "白、灰、蓝色云层属于普通日间云" in SCORING_PROMPT
    assert max(list(CATEGORY_SCORES.values())[:3]) < 50
    assert min(list(CATEGORY_SCORES.values())[3:]) >= 50


def test_parser_uses_last_valid_json_object() -> None:
    output = (
        'noise {"category":"unknown"} more '
        '{"category":"strong_colored_clouds","reason":"  红色 云层  "}'
    )

    result = parse_model_response(output)

    assert result.score == 84
    assert result.reason == "红色 云层"


@pytest.mark.parametrize(
    "output",
    [
        "no json",
        '{"score": 84, "reason": "legacy"}',
        '{"category": true, "reason": "x"}',
        '{"category": "unknown", "reason": "x"}',
        '{"category": "no_evidence", "reason": ""}',
    ],
)
def test_parser_rejects_invalid_responses(output: str) -> None:
    with pytest.raises(InferenceError):
        parse_model_response(output)


def test_runner_sends_prepared_image_and_prompt(tmp_path, monkeypatch) -> None:
    instances = _fake_server(
        monkeypatch,
        iter(['{"category":"colored_clouds","reason":"天空存在橙红色云层"}']),
    )

    with LocalVisionScorer(_environment(tmp_path)) as scorer:
        result = scorer.score(_image(tmp_path))

    assert result.score == 62
    assert instances[0].calls == 1
    assert instances[0].closed


def test_gpu_runner_configures_shared_server_slots(tmp_path, monkeypatch) -> None:
    instances = _fake_server(
        monkeypatch,
        iter(['{"category":"strong_colored_clouds","reason":"明显晚霞"}']),
    )

    with LocalVisionScorer(_environment(tmp_path, backend="cuda")) as scorer:
        scorer.configure_workers(2)
        scorer.score(_image(tmp_path))

    assert instances[0].environment.backend == "cuda"
    assert instances[0].slots == 2


def test_gpu_inference_failure_falls_back_to_cpu(tmp_path, monkeypatch) -> None:
    cpu = _environment(tmp_path / "cpu", backend="cpu")
    restored_gpu = _environment(tmp_path / "restored", backend="cuda")
    instances = _fake_server(
        monkeypatch,
        iter(
            [
                InferenceError("GPU failed"),
                '{"category":"colored_clouds","reason":"CPU fallback"}',
            ]
        ),
    )
    monkeypatch.setattr(
        runner,
        "ensure_runtime_environment",
        lambda *, force_cpu: cpu if force_cpu else restored_gpu,
    )

    with LocalVisionScorer(_environment(tmp_path / "gpu", backend="cuda")) as scorer:
        result = scorer.score(_image(tmp_path))
        assert scorer.inference_backend == "cpu"
        assert scorer.accelerator_fallback_active
        assert scorer.restore_acceleration()
        assert scorer.inference_backend == "cuda"

    assert result.score == 62
    assert [item.environment.backend for item in instances] == ["cuda", "cpu"]
    assert all(item.closed for item in instances)


def test_runner_retries_once_when_json_is_invalid(tmp_path, monkeypatch) -> None:
    instances = _fake_server(
        monkeypatch,
        iter(
            [
                "invalid",
                '{"category":"uncertain_colored_clouds","reason":"证据较弱"}',
            ]
        ),
    )

    with LocalVisionScorer(_environment(tmp_path)) as scorer:
        result = scorer.score(_image(tmp_path))

    assert instances[0].calls == 2
    assert result.score == 42


def test_runner_reports_service_failure(tmp_path, monkeypatch) -> None:
    _fake_server(monkeypatch, iter([InferenceError("model failed")]))

    with LocalVisionScorer(_environment(tmp_path)) as scorer:
        with pytest.raises(InferenceError, match="model failed"):
            scorer.score(_image(tmp_path))


def test_closed_runner_cannot_restart_service(tmp_path, monkeypatch) -> None:
    instances = _fake_server(
        monkeypatch,
        iter(['{"category":"no_colored_clouds","reason":"unused"}']),
    )
    scorer = LocalVisionScorer(_environment(tmp_path))
    scorer.close()

    with pytest.raises(InferenceError, match="已经关闭"):
        scorer.score(_image(tmp_path))

    assert not instances
