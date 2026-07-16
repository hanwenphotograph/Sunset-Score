from __future__ import annotations

from contextlib import contextmanager
import signal
from types import FrameType
from typing import Iterator


class TerminationRequested(BaseException):
    """Request an orderly shutdown after receiving a process signal."""

    def __init__(self, signal_number: int) -> None:
        self.signal_number = signal_number
        try:
            self.signal_name = signal.Signals(signal_number).name
        except ValueError:
            self.signal_name = str(signal_number)
        super().__init__(self.signal_name)


@contextmanager
def handle_termination_signals() -> Iterator[None]:
    previous_handlers: list[tuple[int, object]] = []
    for signal_number in _termination_signals():
        try:
            previous = signal.getsignal(signal_number)
            signal.signal(signal_number, _raise_termination)
        except (OSError, ValueError):
            continue
        previous_handlers.append((signal_number, previous))

    try:
        yield
    finally:
        for signal_number, previous in reversed(previous_handlers):
            signal.signal(signal_number, previous)


def _termination_signals() -> tuple[int, ...]:
    available = (
        getattr(signal, name)
        for name in ("SIGINT", "SIGTERM", "SIGBREAK")
        if hasattr(signal, name)
    )
    return tuple(dict.fromkeys(int(item) for item in available))


def _raise_termination(signal_number: int, frame: FrameType | None) -> None:
    del frame
    raise TerminationRequested(signal_number)
