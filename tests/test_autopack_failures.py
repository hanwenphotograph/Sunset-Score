from __future__ import annotations

from pathlib import Path

import pytest

from sunsetscore.autopack import packer
from sunsetscore.autopack.packer import pack_score_result
from sunsetscore.errors import AutopackError
from sunsetscore.results import ScoreResult, SunsetRange


def _photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(path.name.encode("ascii"))


def _sunset_result(start: str, end: str) -> ScoreResult:
    return ScoreResult(
        average_score=4,
        max_score=4,
        has_sunset=True,
        sunset_ranges=(SunsetRange(start, end),),
    )


def test_missing_range_photo_keeps_previous_output(tmp_path) -> None:
    _photo(tmp_path / "photo1.jpg")
    previous = tmp_path / "SunsetResult" / "previous.jpg"
    _photo(previous)

    with pytest.raises(AutopackError, match="已不存在"):
        pack_score_result(
            tmp_path,
            _sunset_result("missing.jpg", "missing.jpg"),
            recursive=False,
        )

    assert previous.read_bytes() == b"previous.jpg"
    assert list(tmp_path.parent.glob(f".{tmp_path.name}-SunsetResult-*")) == []


def test_copy_failure_keeps_previous_output(tmp_path, monkeypatch) -> None:
    for number in range(1, 4):
        _photo(tmp_path / f"photo{number}.jpg")
    previous = tmp_path / "SunsetResult" / "previous.jpg"
    _photo(previous)
    original_copy = packer.shutil.copy2
    copy_count = 0

    def failing_copy(source, destination):
        nonlocal copy_count
        copy_count += 1
        if copy_count == 2:
            raise OSError("模拟复制失败")
        return original_copy(source, destination)

    monkeypatch.setattr(packer.shutil, "copy2", failing_copy)

    with pytest.raises(AutopackError, match="模拟复制失败"):
        pack_score_result(
            tmp_path,
            _sunset_result("photo1.jpg", "photo3.jpg"),
            recursive=False,
        )

    assert previous.read_bytes() == b"previous.jpg"
    assert list(tmp_path.parent.glob(f".{tmp_path.name}-SunsetResult-*")) == []
