from __future__ import annotations

from pathlib import Path

from .results import ScoreResult
from .service import run_directory_score


def score_directory(
    directory: str | Path,
    *,
    recursive: bool = False,
    interval: int | None = None,
) -> ScoreResult:
    """Score a directory and return only its aggregate conclusion."""

    return run_directory_score(
        Path(directory),
        recursive=recursive,
        interval=interval,
    )
