from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunsetscore import cli
from sunsetscore.errors import InputError
from sunsetscore.results import (
    DirectoryScoreResult,
    IndependentScoreResult,
    SunsetRange,
)


def test_no_arguments_prints_help_without_scoring(capsys, monkeypatch) -> None:
    def unexpected_score(*args, **kwargs):
        raise AssertionError("scoring must not start")

    monkeypatch.setattr(cli, "score_directory", unexpected_score)

    assert cli.main([]) == 0
    output = capsys.readouterr()
    assert "用法: sunsetscore" in output.out
    assert "--recursive" in output.out
    assert "--autopack" in output.out
    assert output.err == ""


def test_options_without_directory_also_print_help(capsys, monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "score_directory",
        lambda *args, **kwargs: pytest.fail("scoring must not start"),
    )

    assert cli.main(["--json", "-r"]) == 0
    assert "用法: sunsetscore" in capsys.readouterr().out


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


def test_independently_requires_recursive_mode(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["photos", "--independently"])

    assert raised.value.code == 2
    assert "只能与 -r/--recursive 一起使用" in capsys.readouterr().err


def test_independent_alias_prints_directories_and_report(capsys, monkeypatch) -> None:
    result = _independent_result()
    calls = []

    def fake_score(
        directory,
        *,
        interval,
        cpu_infer,
        gpu_workers,
        gpu_memory_limit,
        force,
    ):
        calls.append(
            (directory, interval, cpu_infer, gpu_workers, gpu_memory_limit, force)
        )
        return result

    monkeypatch.setattr(cli, "score_directories_independently", fake_score)

    assert cli.main(["photos", "-r", "-ind", "--interval", "5"]) == 0
    output = capsys.readouterr()
    assert calls == [(Path("photos"), 5, False, None, None, False)]
    assert "day-1: 平均分 62.50，最高分 91" in output.out
    assert "晚霞 是，区间 first.jpg 至 third.jpg" in output.out
    assert "分析报告: C:/photos/report.md" in output.out


def test_independent_json_and_partial_failure_return_nonzero(
    capsys,
    monkeypatch,
) -> None:
    result = _independent_result(failed=True)
    monkeypatch.setattr(
        cli,
        "score_directories_independently",
        lambda *args, **kwargs: result,
    )

    assert cli.main(["photos", "-r", "--independently", "--json"]) == 1
    document = json.loads(capsys.readouterr().out)
    assert document["successful_directory_count"] == 1
    assert document["failed_directory_count"] == 1
    assert document["inference_backend"] == "cuda"
    assert document["inference_device"] == "CUDA0: Fake GPU"
    assert document["inference_workers"] == 1
    assert document["gpu_memory_limit_gib"] == 8.5
    assert document["directories"][1]["error"] == "模拟失败"


def _independent_result(*, failed: bool = False) -> IndependentScoreResult:
    directories = [
        DirectoryScoreResult(
            directory="day-1",
            image_count=10,
            sampled_count=1,
            successful_count=1,
            interval=10,
            average_score=62.5,
            max_score=91,
            has_sunset=True,
            sunset_ranges=(SunsetRange("first.jpg", "third.jpg"),),
        )
    ]
    if failed:
        directories.append(DirectoryScoreResult(directory="day-2", error="模拟失败"))
    return IndependentScoreResult(
        root_directory="C:/photos",
        generated_at="2026-07-16T12:00:00+08:00",
        model_version="fake-v1",
        report_path="C:/photos/report.md",
        directories=tuple(directories),
        inference_backend="cuda",
        inference_device="CUDA0: Fake GPU",
        gpu_memory_limit_gib=8.5,
    )
