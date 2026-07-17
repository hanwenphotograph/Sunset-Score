from __future__ import annotations

import signal
from pathlib import Path
from threading import Barrier, Event
from time import perf_counter

import pytest

from sunsetscore import cli
from sunsetscore.inference.batch import score_image_batch
from sunsetscore.results import PhotoScore
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


def test_parallel_batch_does_not_wait_for_workers_after_termination(tmp_path) -> None:
    started = Barrier(2)
    release = Event()

    class InterruptingScorer:
        def score(self, image: Path) -> PhotoScore:
            started.wait(timeout=2)
            if image.name == "interrupt.jpg":
                raise TerminationRequested(signal.SIGTERM)
            release.wait(timeout=2)
            return PhotoScore(1, "unused")

    images = [tmp_path / "interrupt.jpg", tmp_path / "blocked.jpg"]
    before = perf_counter()
    try:
        with pytest.raises(TerminationRequested):
            score_image_batch(images, tmp_path, InterruptingScorer(), workers=2)
    finally:
        release.set()

    assert perf_counter() - before < 1
