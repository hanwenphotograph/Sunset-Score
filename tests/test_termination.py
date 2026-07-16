from __future__ import annotations

import signal

import pytest

from sunsetscore import cli
from sunsetscore.termination import TerminationRequested, handle_termination_signals


def test_termination_handler_raises_and_restores_signal() -> None:
    previous = signal.getsignal(signal.SIGTERM)

    with pytest.raises(TerminationRequested) as raised:
        with handle_termination_signals():
            handler = signal.getsignal(signal.SIGTERM)
            assert callable(handler)
            handler(signal.SIGTERM, None)

    assert raised.value.signal_number == signal.SIGTERM
    assert raised.value.signal_name == "SIGTERM"
    assert signal.getsignal(signal.SIGTERM) == previous


def test_cli_returns_signal_exit_code(capsys, monkeypatch, tmp_path) -> None:
    def terminate(*args, **kwargs):
        signal.raise_signal(signal.SIGTERM)
        pytest.fail("the installed signal handler must stop scoring")

    monkeypatch.setattr(cli, "score_directory", terminate)

    assert cli.main([str(tmp_path)]) == 128 + signal.SIGTERM
    assert "SIGTERM" in capsys.readouterr().err
