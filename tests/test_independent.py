from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pytest

from sunsetscore import independent
from sunsetscore.errors import InferenceError, ScoringError
from sunsetscore.log import configure_logging
from sunsetscore.results import PhotoScore
from sunsetscore.score_file import SCORE_FILENAME
from sunsetscore.independent import run_independent_directory_scores


class FakeScorer:
    model_version = "fake-v1"
    inference_backend = "cuda"
    inference_device = "CUDA0: Fake GPU"

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
        return PhotoScore(self.scores[image.name], "模拟理由")


@pytest.fixture(autouse=True)
def capture_logs() -> StringIO:
    stream = StringIO()
    configure_logging(stream)
    return stream


def _photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake image")


def test_independent_analysis_uses_each_directory_config_and_writes_report(
    tmp_path,
) -> None:
    _photo(tmp_path / "root.jpg")
    _photo(tmp_path / "a2" / "first.jpg")
    _photo(tmp_path / "a2" / "second.jpg")
    _photo(tmp_path / "a2" / "third.jpg")
    _photo(tmp_path / "a10" / "only.jpg")
    (tmp_path / "a2" / ".sunsetscore.toml").write_text(
        "[sampling]\ninterval = 2\n",
        encoding="utf-8",
    )
    scorer = FakeScorer({"first.jpg": 1, "third.jpg": 4, "only.jpg": 2})
    timestamp = datetime(2026, 7, 16, 12, 34, 56, tzinfo=timezone.utc)

    result = run_independent_directory_scores(
        tmp_path,
        interval=None,
        scorer=scorer,
        generated_at=timestamp,
    )

    assert [item.directory for item in result.directories] == ["a2", "a10"]
    first, second = result.directories
    assert first.interval == 2
    assert first.image_count == 3
    assert first.sampled_count == 2
    assert first.average_score == 2.5
    assert first.max_score == 4
    assert second.interval == 10
    assert second.average_score == 2.0
    assert (tmp_path / "a2" / SCORE_FILENAME).is_file()
    assert (tmp_path / "a10" / SCORE_FILENAME).is_file()
    assert "root.jpg" not in scorer.seen
    assert Path(result.report_path).name == "sunsetscore-analysis-20260716-123456.md"
    report = Path(result.report_path).read_text(encoding="utf-8")
    assert "# SunsetScore 独立目录分析报告" in report
    assert "- 推理后端：`CUDA`" in report
    assert "- 推理设备：`CUDA0: Fake GPU`" in report
    assert "- 推理服务槽位：`1`" in report
    assert (
        "| a2 | 3 | 2 | 2 | 0 | 2 | 1 | 2.50 | 4 | 是 | third.jpg | 成功 |"
        in report
    )


def test_independent_analysis_reports_failed_directory_and_continues(tmp_path) -> None:
    _photo(tmp_path / "bad" / "bad.jpg")
    _photo(tmp_path / "good" / "good.jpg")
    scorer = FakeScorer({"good.jpg": 4}, failures={"bad.jpg"})

    result = run_independent_directory_scores(
        tmp_path,
        interval=1,
        scorer=scorer,
        generated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert result.successful_directory_count == 1
    assert result.failed_directory_count == 1
    assert result.directories[0].directory == "bad"
    assert "所有采样照片" in (result.directories[0].error or "")
    assert result.directories[1].average_score == 4.0
    assert not (tmp_path / "bad" / SCORE_FILENAME).exists()
    assert (tmp_path / "good" / SCORE_FILENAME).is_file()
    report = Path(result.report_path).read_text(encoding="utf-8")
    assert "## 失败详情" in report
    assert "`bad`" in report


def test_cached_run_reuses_report_and_new_inference_creates_report(tmp_path) -> None:
    _photo(tmp_path / "child" / "photo.jpg")
    scorer = FakeScorer({"photo.jpg": 1})
    timestamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    first = run_independent_directory_scores(
        tmp_path,
        interval=1,
        scorer=scorer,
        generated_at=timestamp,
    )
    second = run_independent_directory_scores(
        tmp_path,
        interval=1,
        scorer=scorer,
        generated_at=timestamp,
    )
    third = run_independent_directory_scores(
        tmp_path,
        interval=1,
        scorer=scorer,
        generated_at=timestamp,
        force=True,
    )
    fourth = run_independent_directory_scores(
        tmp_path,
        interval=1,
        scorer=scorer,
        generated_at=timestamp,
    )

    assert Path(first.report_path).name == "sunsetscore-analysis-20260102-030405.md"
    assert second.report_path == first.report_path
    assert Path(third.report_path).name == "sunsetscore-analysis-20260102-030405-2.md"
    assert fourth.report_path == third.report_path


def test_independent_analysis_requires_a_valid_descendant_directory(tmp_path) -> None:
    _photo(tmp_path / "root.jpg")

    with pytest.raises(ScoringError, match="合法子目录"):
        run_independent_directory_scores(
            tmp_path,
            interval=1,
            scorer=FakeScorer({"root.jpg": 1}),
        )


def test_independent_analysis_closes_shared_owned_scorer(tmp_path, monkeypatch) -> None:
    _photo(tmp_path / "child" / "photo.jpg")
    instances = []

    class ManagedScorer(FakeScorer):
        def __init__(self, *, cpu_infer):
            del cpu_infer
            super().__init__({"photo.jpg": 3})
            self.closed = False
            instances.append(self)

        def close(self):
            self.closed = True

    monkeypatch.setattr(independent, "LocalVisionScorer", ManagedScorer)

    run_independent_directory_scores(tmp_path, interval=1)

    assert instances[0].closed
