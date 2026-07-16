from __future__ import annotations

from pathlib import Path

from .independent import run_independent_directory_scores
from .results import IndependentScoreResult, ScoreResult
from .service import run_directory_score


def score_directory(
    directory: str | Path,
    *,
    recursive: bool = False,
    interval: int | None = None,
    cpu_infer: bool = False,
    gpu_workers: int | None = None,
    gpu_memory_limit: float | None = None,
) -> ScoreResult:
    """Score a directory, optionally forcing CPU inference."""

    return run_directory_score(
        Path(directory),
        recursive=recursive,
        interval=interval,
        cpu_infer=cpu_infer,
        gpu_workers=gpu_workers,
        gpu_memory_limit=gpu_memory_limit,
    )


def score_directories_independently(
    directory: str | Path,
    *,
    interval: int | None = None,
    cpu_infer: bool = False,
    gpu_workers: int | None = None,
    gpu_memory_limit: float | None = None,
) -> IndependentScoreResult:
    """Score descendant directories and write a Markdown report."""

    return run_independent_directory_scores(
        Path(directory),
        interval=interval,
        cpu_infer=cpu_infer,
        gpu_workers=gpu_workers,
        gpu_memory_limit=gpu_memory_limit,
    )
