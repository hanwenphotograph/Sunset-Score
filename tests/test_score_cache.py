from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunsetscore import independent
from sunsetscore.independent import run_independent_directory_scores
from sunsetscore.results import PhotoScore
from sunsetscore.score_file import SCORE_FILENAME
from sunsetscore.service import run_directory_score
from sunsetscore.version import __version__


class FakeScorer:
    model_version = "fake-v1"
    inference_backend = "cpu"
    inference_device = "Fake CPU"
    parallel_scoring_supported = False
    free_gpu_memory_mib = None

    def __init__(self, scores: dict[str, int]) -> None:
        self.scores = scores
        self.seen: list[str] = []

    def score(self, image: Path) -> PhotoScore:
        self.seen.append(image.name)
        return PhotoScore(self.scores[image.name], "模拟理由")


def _photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake image")


def test_completed_score_is_written_and_reused(tmp_path) -> None:
    _photo(tmp_path / "photo.jpg")
    first_scorer = FakeScorer({"photo.jpg": 25})

    first = run_directory_score(
        tmp_path,
        recursive=False,
        interval=1,
        scorer=first_scorer,
    )

    score_path = tmp_path / SCORE_FILENAME
    document = json.loads(score_path.read_text(encoding="utf-8"))
    assert document["format_version"] == 2
    assert document["application_version"] == __version__
    assert document["model_version"] == "fake-v1"
    assert document["result"]["average_score"] == 25.0
    assert document["result"]["has_sunset"] is False
    assert document["sample_scores"][0]["photo"] == "photo.jpg"

    second_scorer = FakeScorer({"photo.jpg": 90})
    second = run_directory_score(
        tmp_path,
        recursive=False,
        interval=1,
        scorer=second_scorer,
    )

    assert second == first
    assert second_scorer.seen == []


def test_force_rescores_and_overwrites_score_file(tmp_path) -> None:
    _photo(tmp_path / "photo.jpg")
    run_directory_score(
        tmp_path,
        recursive=False,
        interval=1,
        scorer=FakeScorer({"photo.jpg": 25}),
    )
    scorer = FakeScorer({"photo.jpg": 90})

    result = run_directory_score(
        tmp_path,
        recursive=False,
        interval=1,
        scorer=scorer,
        force=True,
    )

    document = json.loads((tmp_path / SCORE_FILENAME).read_text(encoding="utf-8"))
    assert result.average_score == 90.0
    assert scorer.seen == ["photo.jpg"]
    assert document["result"]["average_score"] == 90.0


def test_different_recursive_scope_is_not_reused(tmp_path) -> None:
    _photo(tmp_path / "root.jpg")
    _photo(tmp_path / "child" / "nested.jpg")
    run_directory_score(
        tmp_path,
        recursive=False,
        interval=1,
        scorer=FakeScorer({"root.jpg": 20}),
    )
    scorer = FakeScorer({"root.jpg": 20, "nested.jpg": 80})

    result = run_directory_score(
        tmp_path,
        recursive=True,
        interval=1,
        scorer=scorer,
    )

    assert result.average_score == 50.0
    assert set(scorer.seen) == {"root.jpg", "nested.jpg"}


def test_invalid_score_file_is_replaced(tmp_path) -> None:
    _photo(tmp_path / "photo.jpg")
    (tmp_path / SCORE_FILENAME).write_text("not json", encoding="utf-8")
    scorer = FakeScorer({"photo.jpg": 40})

    result = run_directory_score(
        tmp_path,
        recursive=False,
        interval=1,
        scorer=scorer,
    )

    assert result.average_score == 40.0
    assert scorer.seen == ["photo.jpg"]
    json.loads((tmp_path / SCORE_FILENAME).read_text(encoding="utf-8"))


def test_older_application_cache_is_replaced(tmp_path) -> None:
    _photo(tmp_path / "photo.jpg")
    run_directory_score(
        tmp_path,
        recursive=False,
        interval=1,
        scorer=FakeScorer({"photo.jpg": 25}),
    )
    score_path = tmp_path / SCORE_FILENAME
    document = json.loads(score_path.read_text(encoding="utf-8"))
    document["application_version"] = "0.6.0"
    score_path.write_text(json.dumps(document), encoding="utf-8")
    scorer = FakeScorer({"photo.jpg": 75})

    result = run_directory_score(
        tmp_path,
        recursive=False,
        interval=1,
        scorer=scorer,
    )

    replaced = json.loads(score_path.read_text(encoding="utf-8"))
    assert scorer.seen == ["photo.jpg"]
    assert result.has_sunset is True
    assert replaced["application_version"] == __version__
    assert replaced["result"]["max_score"] == 75


def test_independent_mode_uses_all_cached_scores_without_loading_model(
    tmp_path,
    monkeypatch,
) -> None:
    _photo(tmp_path / "day1" / "one.jpg")
    _photo(tmp_path / "day2" / "two.jpg")
    first = run_independent_directory_scores(
        tmp_path,
        interval=1,
        scorer=FakeScorer({"one.jpg": 30, "two.jpg": 70}),
    )
    monkeypatch.setattr(
        independent,
        "LocalVisionScorer",
        lambda **kwargs: pytest.fail("cached run must not initialize the model"),
    )

    second = run_independent_directory_scores(tmp_path, interval=1)

    assert [item.average_score for item in second.directories] == [30.0, 70.0]
    assert second.model_version == first.model_version
    assert Path(second.report_path).is_file()

    forced_scorer = FakeScorer({"one.jpg": 40, "two.jpg": 80})
    forced = run_independent_directory_scores(
        tmp_path,
        interval=1,
        scorer=forced_scorer,
        force=True,
    )
    assert forced_scorer.seen == ["one.jpg", "two.jpg"]
    assert [item.average_score for item in forced.directories] == [40.0, 80.0]
