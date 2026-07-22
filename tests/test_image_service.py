from __future__ import annotations

from pathlib import Path

from sunsetscore import api, image_service
from sunsetscore.results import PhotoScore


class FakeScorer:
    model_version = "fake-v1"
    inference_backend = "cpu"
    inference_device = "Test CPU"
    parallel_scoring_supported = False
    free_gpu_memory_mib = None

    def __init__(self) -> None:
        self.seen: list[Path] = []

    def score(self, image: Path) -> PhotoScore:
        self.seen.append(image)
        return PhotoScore(4, "云层呈现大范围鲜艳着色")


def test_image_service_scores_exact_input_file(tmp_path) -> None:
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"handled by fake scorer")
    scorer = FakeScorer()

    result = image_service.run_image_score(image, scorer=scorer)

    assert result == PhotoScore(4, "云层呈现大范围鲜艳着色")
    assert scorer.seen == [image.resolve()]


def test_image_service_closes_owned_scorer(tmp_path, monkeypatch) -> None:
    image = tmp_path / "photo.png"
    image.write_bytes(b"handled by fake scorer")
    instances = []

    class ManagedScorer(FakeScorer):
        def __init__(self, *, cpu_infer: bool) -> None:
            super().__init__()
            self.cpu_infer = cpu_infer
            self.closed = False
            instances.append(self)

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(image_service, "LocalVisionScorer", ManagedScorer)

    result = image_service.run_image_score(image, cpu_infer=True)

    assert result.score == 4
    assert instances[0].cpu_infer is True
    assert instances[0].closed


def test_public_image_api_forwards_path_and_runtime_options(monkeypatch) -> None:
    calls = []
    expected = PhotoScore(2, "普通云层")

    def fake_run(path, **kwargs):
        calls.append((path, kwargs))
        return expected

    monkeypatch.setattr(api, "run_image_score", fake_run)

    result = api.score_image(
        "photos/example.jpg",
        gpu_workers=1,
        gpu_memory_limit=6,
    )

    assert result is expected
    assert calls == [
        (
            Path("photos/example.jpg"),
            {
                "cpu_infer": False,
                "gpu_workers": 1,
                "gpu_memory_limit": 6,
            },
        )
    ]
