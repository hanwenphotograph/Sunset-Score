from __future__ import annotations

from pathlib import Path

import pytest

from sunsetscore import cli
from sunsetscore.results import ScoreResult


def test_cpu_infer_is_forwarded_to_api(capsys, monkeypatch) -> None:
    calls = []

    def fake_score(
        directory,
        *,
        recursive,
        interval,
        cpu_infer,
        gpu_workers,
        gpu_memory_limit,
        force,
    ):
        calls.append(
            (
                directory,
                recursive,
                interval,
                cpu_infer,
                gpu_workers,
                gpu_memory_limit,
                force,
            )
        )
        return ScoreResult(average_score=2.0, max_score=2)

    monkeypatch.setattr(cli, "score_directory", fake_score)

    assert cli.main(["photos", "--cpu-infer"]) == 0
    assert calls == [(Path("photos"), False, None, True, None, None, False)]
    assert "平均分: 2.00" in capsys.readouterr().out


def test_gpu_limits_are_forwarded_to_api(capsys, monkeypatch) -> None:
    calls = []

    def fake_score(directory, **kwargs):
        calls.append((directory, kwargs))
        return ScoreResult(average_score=2.0, max_score=2)

    monkeypatch.setattr(cli, "score_directory", fake_score)

    assert cli.main(["photos", "--gpu-workers", "2", "--gpu-memory-limit", "8.5"]) == 0
    assert calls[0][1]["gpu_workers"] == 2
    assert calls[0][1]["gpu_memory_limit"] == 8.5
    capsys.readouterr()


def test_force_is_forwarded_to_api(capsys, monkeypatch) -> None:
    calls = []

    def fake_score(directory, **kwargs):
        calls.append((directory, kwargs))
        return ScoreResult(average_score=2.0, max_score=2)

    monkeypatch.setattr(cli, "score_directory", fake_score)

    assert cli.main(["photos", "--force"]) == 0
    assert calls[0][1]["force"] is True
    capsys.readouterr()


def test_cpu_infer_rejects_gpu_limits(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["photos", "--cpu-infer", "--gpu-workers", "2"])

    assert raised.value.code == 2
    assert "不能与 GPU 限制参数一起使用" in capsys.readouterr().err


def test_gpu_memory_limit_has_safe_minimum(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["photos", "--gpu-memory-limit", "2.5"])

    assert raised.value.code == 2
    assert "必须大于等于 3 GiB" in capsys.readouterr().err


def test_gpu_workers_cannot_exceed_server_slot_limit(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["photos", "--gpu-workers", "3"])

    assert raised.value.code == 2
    assert "必须小于等于 2" in capsys.readouterr().err
