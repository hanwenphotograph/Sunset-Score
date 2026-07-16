from __future__ import annotations

from concurrent.futures import as_completed, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Protocol, Sequence

from ..errors import PhotoProcessingError
from ..log import logger
from ..results import PhotoScore


class PhotoScorer(Protocol):
    def score(self, image: Path) -> PhotoScore: ...


@dataclass(frozen=True, slots=True)
class BatchScoreResult:
    scores: tuple[int, ...]
    failed_count: int


@dataclass(frozen=True, slots=True)
class _PhotoOutcome:
    index: int
    image: Path
    elapsed: float
    score: PhotoScore | None = None
    error: PhotoProcessingError | None = None


def score_image_batch(
    images: Sequence[Path],
    root: Path,
    scorer: PhotoScorer,
    *,
    workers: int,
) -> BatchScoreResult:
    if workers == 1:
        outcomes = _score_serially(images, root, scorer)
    else:
        outcomes = _score_concurrently(images, root, scorer, workers)
    scores = tuple(
        outcome.score.score for outcome in outcomes if outcome.score is not None
    )
    return BatchScoreResult(
        scores=scores,
        failed_count=sum(outcome.error is not None for outcome in outcomes),
    )


def _score_serially(
    images: Sequence[Path],
    root: Path,
    scorer: PhotoScorer,
) -> list[_PhotoOutcome]:
    outcomes = []
    for index, image in enumerate(images, start=1):
        relative = image.relative_to(root)
        logger.info("[%d/%d] 正在评分：%s", index, len(images), relative)
        outcome = _score_one(index, image, scorer)
        _log_outcome(outcome, root, len(images))
        outcomes.append(outcome)
    return outcomes


def _score_concurrently(
    images: Sequence[Path],
    root: Path,
    scorer: PhotoScorer,
    workers: int,
) -> list[_PhotoOutcome]:
    outcomes: list[_PhotoOutcome | None] = [None] * len(images)
    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix="sunsetscore-gpu",
    ) as executor:
        futures = {}
        for index, image in enumerate(images, start=1):
            relative = image.relative_to(root)
            logger.info(
                "[%d/%d] 已加入 GPU 评分队列：%s",
                index,
                len(images),
                relative,
            )
            future = executor.submit(_score_one, index, image, scorer)
            futures[future] = index - 1
        for future in as_completed(futures):
            outcome = future.result()
            outcomes[futures[future]] = outcome
            _log_outcome(outcome, root, len(images))
    return [outcome for outcome in outcomes if outcome is not None]


def _score_one(index: int, image: Path, scorer: PhotoScorer) -> _PhotoOutcome:
    started = perf_counter()
    try:
        score = scorer.score(image)
    except PhotoProcessingError as exc:
        return _PhotoOutcome(
            index=index,
            image=image,
            elapsed=perf_counter() - started,
            error=exc,
        )
    return _PhotoOutcome(
        index=index,
        image=image,
        elapsed=perf_counter() - started,
        score=score,
    )


def _log_outcome(outcome: _PhotoOutcome, root: Path, total: int) -> None:
    relative = outcome.image.relative_to(root)
    if outcome.error is not None:
        logger.warning(
            "[%d/%d] 跳过 %s：%s",
            outcome.index,
            total,
            relative,
            outcome.error,
        )
        return
    assert outcome.score is not None
    logger.info(
        "[%d/%d] 得分 %d，耗时 %.2f 秒，理由：%s",
        outcome.index,
        total,
        outcome.score.score,
        outcome.elapsed,
        outcome.score.reason,
    )
