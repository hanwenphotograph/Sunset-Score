from __future__ import annotations

import json

from sunsetscore import cli
from sunsetscore.autopack.packer import AutopackResult
from sunsetscore.results import ScoreResult, SunsetRange


def test_json_mode_prints_only_conclusion(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        cli,
        "score_directory",
        lambda *args, **kwargs: ScoreResult(
            average_score=62.5,
            max_score=91,
            has_sunset=True,
            sunset_ranges=(SunsetRange("one.jpg", "three.jpg"),),
        ),
    )

    assert cli.main([str(tmp_path), "--json"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out) == {
        "average_score": 62.5,
        "max_score": 91,
        "has_sunset": True,
        "sunset_ranges": [
            {"start_photo": "one.jpg", "end_photo": "three.jpg"}
        ],
    }
    assert output.err == ""


def test_autopack_keeps_json_stdout_machine_readable(
    capsys,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        cli,
        "score_directory",
        lambda *args, **kwargs: ScoreResult(average_score=20, max_score=20),
    )
    monkeypatch.setattr(
        cli,
        "pack_score_result",
        lambda *args, **kwargs: AutopackResult(tmp_path / "SunsetResult", 0, 0),
    )

    assert cli.main([str(tmp_path), "--autopack", "--json"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "average_score": 20,
        "max_score": 20,
        "has_sunset": False,
        "sunset_ranges": [],
    }


def test_text_mode_formats_average_to_two_places(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        cli,
        "score_directory",
        lambda *args, **kwargs: ScoreResult(average_score=7.0, max_score=7),
    )

    assert cli.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out == (
        "平均分: 7.00\n"
        "最高分: 7\n"
        "检测到晚霞: 否\n"
        "晚霞区间: -\n"
    )
