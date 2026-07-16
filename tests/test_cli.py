from __future__ import annotations

import json

import pytest

from sunsetscore import cli
from sunsetscore.errors import InputError
from sunsetscore.results import ScoreResult


def test_no_arguments_prints_help_without_scoring(capsys, monkeypatch) -> None:
    def unexpected_score(*args, **kwargs):
        raise AssertionError("scoring must not start")

    monkeypatch.setattr(cli, "score_directory", unexpected_score)

    assert cli.main([]) == 0
    output = capsys.readouterr()
    assert "用法: sunsetscore" in output.out
    assert "--recursive" in output.out
    assert output.err == ""


def test_options_without_directory_also_print_help(capsys, monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "score_directory",
        lambda *args, **kwargs: pytest.fail("scoring must not start"),
    )

    assert cli.main(["--json", "-r"]) == 0
    assert "用法: sunsetscore" in capsys.readouterr().out


def test_json_mode_prints_only_conclusion(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        cli,
        "score_directory",
        lambda *args, **kwargs: ScoreResult(average_score=62.5, max_score=91),
    )

    assert cli.main([str(tmp_path), "--json"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out) == {"average_score": 62.5, "max_score": 91}
    assert output.err == ""


def test_text_mode_formats_average_to_two_places(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        cli,
        "score_directory",
        lambda *args, **kwargs: ScoreResult(average_score=7.0, max_score=7),
    )

    assert cli.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out == "平均分: 7.00\n最高分: 7\n"


def test_expected_error_is_logged_to_stderr(capsys, monkeypatch, tmp_path) -> None:
    def fail(*args, **kwargs):
        raise InputError("输入目录不存在")

    monkeypatch.setattr(cli, "score_directory", fail)

    assert cli.main([str(tmp_path), "--json"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "输入目录不存在" in output.err


def test_invalid_interval_exits_with_usage(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["photos", "--interval", "0"])

    assert raised.value.code == 2
    assert "必须大于等于 1" in capsys.readouterr().err
