from __future__ import annotations

from pathlib import Path

from .image_service import run_image_score
from .independent import run_independent_directory_scores
from .results import IndependentScoreResult, PhotoScore, ScoreResult
from .service import run_directory_score


def score_image(
    image: str | Path,
    *,
    cpu_infer: bool = False,
    gpu_workers: int | None = None,
    gpu_memory_limit: float | None = None,
) -> PhotoScore:
    """Score one supported image and return the model's reason."""

    return run_image_score(
        Path(image),
        cpu_infer=cpu_infer,
        gpu_workers=gpu_workers,
        gpu_memory_limit=gpu_memory_limit,
    )


def score_directory(
    directory: str | Path,
    *,
    recursive: bool = False,
    interval: int | None = None,
    cpu_infer: bool = False,
    gpu_workers: int | None = None,
    gpu_memory_limit: float | None = None,
    force: bool = False,
) -> ScoreResult:
    """Detect sunset-glow ranges, reusing its score file unless forced."""

    return run_directory_score(
        Path(directory),
        recursive=recursive,
        interval=interval,
        cpu_infer=cpu_infer,
        gpu_workers=gpu_workers,
        gpu_memory_limit=gpu_memory_limit,
        force=force,
    )


def score_directories_independently(
    directory: str | Path,
    *,
    interval: int | None = None,
    cpu_infer: bool = False,
    gpu_workers: int | None = None,
    gpu_memory_limit: float | None = None,
    force: bool = False,
) -> IndependentScoreResult:
    """Score uncached descendant directories and write a Markdown report."""

    return run_independent_directory_scores(
        Path(directory),
        interval=interval,
        cpu_infer=cpu_infer,
        gpu_workers=gpu_workers,
        gpu_memory_limit=gpu_memory_limit,
        force=force,
    )
