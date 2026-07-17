from __future__ import annotations

from pathlib import Path

import pytest

from sunsetscore import cli, service
from sunsetscore.autopack.packer import (
    pack_independent_result,
    pack_score_result,
)
from sunsetscore.results import (
    DirectoryScoreResult,
    IndependentScoreResult,
    PhotoScore,
    ScoreResult,
    SunsetRange,
)
from sunsetscore.service import run_directory_score


def _photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(path.name.encode("ascii"))


def _relative_photos(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*.jpg")
    )


def test_single_result_copies_complete_ranges_and_replaces_output(tmp_path) -> None:
    for number in range(1, 9):
        _photo(tmp_path / f"photo{number}.jpg")
    _photo(tmp_path / "SunsetResult" / "stale.jpg")
    result = ScoreResult(
        average_score=30,
        max_score=75,
        has_sunset=True,
        sunset_ranges=(
            SunsetRange("photo2.jpg", "photo4.jpg"),
            SunsetRange("photo7.jpg", "photo7.jpg"),
        ),
    )

    packed = pack_score_result(tmp_path, result, recursive=False)

    assert packed.photo_count == 4
    assert packed.source_directory_count == 1
    assert _relative_photos(packed.output_directory) == [
        "photo2.jpg",
        "photo3.jpg",
        "photo4.jpg",
        "photo7.jpg",
    ]


def test_recursive_result_preserves_relative_directories(tmp_path) -> None:
    for name in ("a/photo1.jpg", "a/photo2.jpg", "a/photo3.jpg", "b/photo1.jpg"):
        _photo(tmp_path / name)
    result = ScoreResult(
        average_score=60,
        max_score=75,
        has_sunset=True,
        sunset_ranges=(SunsetRange("a/photo2.jpg", "b/photo1.jpg"),),
    )

    packed = pack_score_result(tmp_path, result, recursive=True)

    assert _relative_photos(packed.output_directory) == [
        "a/photo2.jpg",
        "a/photo3.jpg",
        "b/photo1.jpg",
    ]


def test_independent_result_separates_source_directories(tmp_path) -> None:
    for directory, count in (("day1", 5), ("day2", 3), ("day3", 2)):
        for number in range(1, count + 1):
            _photo(tmp_path / directory / f"photo{number}.jpg")
    result = _independent_result(
        DirectoryScoreResult(
            directory="day1",
            has_sunset=True,
            sunset_ranges=(SunsetRange("photo2.jpg", "photo4.jpg"),),
        ),
        DirectoryScoreResult(
            directory="day2",
            has_sunset=True,
            sunset_ranges=(SunsetRange("photo2.jpg", "photo2.jpg"),),
        ),
        DirectoryScoreResult(directory="day3", has_sunset=False),
    )

    packed = pack_independent_result(tmp_path, result)

    assert packed.photo_count == 4
    assert packed.source_directory_count == 2
    assert _relative_photos(packed.output_directory) == [
        "day1/photo2.jpg",
        "day1/photo3.jpg",
        "day1/photo4.jpg",
        "day2/photo2.jpg",
    ]


def test_no_sunset_creates_an_empty_managed_directory(tmp_path) -> None:
    _photo(tmp_path / "photo.jpg")
    _photo(tmp_path / "SunsetResult" / "stale.jpg")

    packed = pack_score_result(
        tmp_path,
        ScoreResult(average_score=20, max_score=20),
        recursive=False,
    )

    assert packed.output_directory.is_dir()
    assert list(packed.output_directory.iterdir()) == []


def test_cli_autopack_reuses_compatible_score_cache(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    _photo(tmp_path / "photo.jpg")
    run_directory_score(
        tmp_path,
        recursive=False,
        interval=1,
        scorer=_FakeScorer(),
    )
    monkeypatch.setattr(
        service,
        "LocalVisionScorer",
        lambda **kwargs: pytest.fail("compatible cache must avoid inference"),
    )

    assert cli.main([str(tmp_path), "--autopack"]) == 0

    output = capsys.readouterr().out
    assert "已打包照片: 1 张" in output
    assert (tmp_path / "SunsetResult" / "photo.jpg").is_file()


def _independent_result(*items: DirectoryScoreResult) -> IndependentScoreResult:
    return IndependentScoreResult(
        root_directory="unused",
        generated_at="2026-07-17T00:00:00+08:00",
        model_version="fake-v1",
        report_path="unused.md",
        directories=items,
    )


class _FakeScorer:
    model_version = "fake-v1"
    inference_backend = "cpu"
    inference_device = "Fake CPU"
    parallel_scoring_supported = False
    free_gpu_memory_mib = None

    def score(self, image: Path) -> PhotoScore:
        return PhotoScore(75, f"{image.name} 存在明显晚霞")
