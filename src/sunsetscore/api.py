from __future__ import annotations

from pathlib import Path

from .results import IndependentScoreResult, ScoreResult
from .service import run_directory_score, run_independent_directory_scores


def score_directory(
    directory: str | Path,
    *,
    recursive: bool = False,
    interval: int | None = None,
    cpu_infer: bool = False,
) -> ScoreResult:
    """Score a directory, optionally forcing CPU inference."""

    return run_directory_score(
        Path(directory),
        recursive=recursive,
        interval=interval,
        cpu_infer=cpu_infer,
    )


def score_directories_independently(
    directory: str | Path,
    *,
    interval: int | None = None,
    cpu_infer: bool = False,
) -> IndependentScoreResult:
    """Score descendant directories and write a Markdown report."""

    return run_independent_directory_scores(
        Path(directory),
        interval=interval,
        cpu_infer=cpu_infer,
    )
