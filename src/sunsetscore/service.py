from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from time import perf_counter
from typing import Protocol

from .config import resolve_interval
from .discovery import discover_images, sample_images
from .errors import PhotoProcessingError, ScoringError
from .inference.runner import LocalVisionScorer
from .log import logger
from .results import PhotoScore, ScoreResult


class ImageScorer(Protocol):
    @property
    def model_version(self) -> str: ...

    def score(self, image: Path) -> PhotoScore: ...


def run_directory_score(
    directory: Path,
    *,
    recursive: bool,
    interval: int | None,
    scorer: ImageScorer | None = None,
) -> ScoreResult:
    images = discover_images(directory, recursive=recursive)
    root = directory.expanduser().resolve()
    resolved_interval = resolve_interval(root, interval)
    if not images:
        raise ScoringError("输入目录中没有可评分的 JPG 或 PNG 照片")

    samples = sample_images(images, resolved_interval)
    logger.info("扫描完成：共 %d 张照片，采样 %d 张", len(images), len(samples))
    logger.info(
        "采样间隔：%d，递归扫描：%s", resolved_interval, "是" if recursive else "否"
    )

    active_scorer = scorer or LocalVisionScorer()
    logger.info("评分模型：%s", active_scorer.model_version)
    scores: list[int] = []
    failed = 0

    for index, image in enumerate(samples, start=1):
        relative = image.relative_to(root)
        started = perf_counter()
        logger.info("[%d/%d] 正在评分：%s", index, len(samples), relative)
        try:
            photo_score = active_scorer.score(image)
        except PhotoProcessingError as exc:
            failed += 1
            logger.warning("[%d/%d] 跳过 %s：%s", index, len(samples), relative, exc)
            continue

        elapsed = perf_counter() - started
        scores.append(photo_score.score)
        logger.info(
            "[%d/%d] 得分 %d，耗时 %.2f 秒，理由：%s",
            index,
            len(samples),
            photo_score.score,
            elapsed,
            photo_score.reason,
        )

    if not scores:
        raise ScoringError("所有采样照片均评分失败，无法生成运行结果")

    result = ScoreResult(
        average_score=_rounded_average(scores),
        max_score=max(scores),
    )
    logger.info("评分完成：成功 %d 张，失败 %d 张", len(scores), failed)
    return result


def _rounded_average(scores: list[int]) -> float:
    value = Decimal(sum(scores)) / Decimal(len(scores))
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
