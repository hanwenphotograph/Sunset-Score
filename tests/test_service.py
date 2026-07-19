from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from sunsetscore import service
from sunsetscore.errors import InferenceError, ScoringError
from sunsetscore.log import configure_logging
from sunsetscore.results import PhotoScore
from sunsetscore.service import run_directory_score


class FakeScorer:
    model_version = "fake-v1"

    def __init__(
        self, scores: dict[str, int], failures: set[str] | None = None
    ) -> None:
        self.scores = scores
        self.failures = failures or set()
        self.seen: list[str] = []

    def score(self, image: Path) -> PhotoScore:
        self.seen.append(image.name)
        if image.name in self.failures:
            raise InferenceError("模拟失败")
        return PhotoScore(self.scores[image.name], f"{image.name} 的理由")


@pytest.fixture(autouse=True)
def capture_service_logs() -> StringIO:
    stream = StringIO()
    configure_logging(stream)
    return stream


def _photos(directory: Path, names: list[str]) -> None:
    for name in names:
        (directory / name).write_bytes(b"not decoded by fake scorer")


def test_service_uses_natural_order_and_interval(tmp_path) -> None:
    _photos(tmp_path, ["photo10.jpg", "photo2.jpg", "photo1.jpg"])
    scorer = FakeScorer({"photo1.jpg": 1, "photo10.jpg": 5})

    result = run_directory_score(
        tmp_path,
        recursive=False,
        interval=2,
        scorer=scorer,
    )

    assert scorer.seen == ["photo1.jpg", "photo10.jpg"]
    assert result.average_score == 3.0
    assert result.max_score == 5


def test_service_reads_interval_from_local_config(tmp_path) -> None:
    _photos(tmp_path, [f"{number}.jpg" for number in range(1, 5)])
    (tmp_path / ".sunsetscore.toml").write_text(
        "[sampling]\ninterval = 2\n",
        encoding="utf-8",
    )
    scorer = FakeScorer({"1.jpg": 1, "3.jpg": 3})

    result = run_directory_score(
        tmp_path,
        recursive=False,
        interval=None,
        scorer=scorer,
    )

    assert scorer.seen == ["1.jpg", "3.jpg"]
    assert result.average_score == 2.0


def test_failed_sample_is_skipped_without_replacement(tmp_path) -> None:
    _photos(tmp_path, ["1.jpg", "2.jpg", "3.jpg", "4.jpg"])
    scorer = FakeScorer({"3.jpg": 4}, failures={"1.jpg"})

    result = run_directory_score(
        tmp_path,
        recursive=False,
        interval=2,
        scorer=scorer,
    )

    assert scorer.seen == ["1.jpg", "3.jpg"]
    assert result.average_score == 4.0
    assert result.max_score == 4


def test_average_uses_round_half_up(tmp_path) -> None:
    names = [f"{number}.jpg" for number in range(1, 9)]
    _photos(tmp_path, names)
    scores = {name: (1 if name == "1.jpg" else 0) for name in names}

    result = run_directory_score(
        tmp_path,
        recursive=False,
        interval=1,
        scorer=FakeScorer(scores),
    )

    assert result.average_score == 0.13


def test_all_failed_samples_produce_no_fake_result(tmp_path) -> None:
    _photos(tmp_path, ["1.jpg"])
    scorer = FakeScorer({}, failures={"1.jpg"})

    with pytest.raises(ScoringError, match="所有采样照片"):
        run_directory_score(tmp_path, recursive=False, interval=10, scorer=scorer)


def test_empty_directory_fails(tmp_path) -> None:
    with pytest.raises(ScoringError, match="没有可评分"):
        run_directory_score(
            tmp_path,
            recursive=False,
            interval=None,
            scorer=FakeScorer({}),
        )


def test_service_closes_owned_local_scorer(tmp_path, monkeypatch) -> None:
    _photos(tmp_path, ["photo.jpg"])
    instances = []

    class ManagedScorer(FakeScorer):
        model_version = "managed-v1"

        def __init__(self, *, cpu_infer):
            del cpu_infer
            super().__init__({"photo.jpg": 4})
            self.closed = False
            instances.append(self)

        def close(self):
            self.closed = True

    monkeypatch.setattr(service, "LocalVisionScorer", ManagedScorer)

    run_directory_score(tmp_path, recursive=False, interval=1)

    assert instances[0].closed
