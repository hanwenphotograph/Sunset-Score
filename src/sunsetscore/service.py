from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from time import perf_counter
from typing import Protocol

from .config import resolve_interval
from .discovery import discover_image_directories, discover_images, sample_images
from .errors import PhotoProcessingError, ScoringError, SunsetScoreError
from .inference.runner import LocalVisionScorer
from .log import logger
from .reporting import write_markdown_report
from .results import (
    DirectoryScoreResult,
    IndependentScoreResult,
    PhotoScore,
    ScoreResult,
)


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
    detail = run_directory_analysis(
        directory,
        recursive=recursive,
        interval=interval,
        scorer=scorer,
    )
    assert detail.average_score is not None
    assert detail.max_score is not None
    return ScoreResult(
        average_score=detail.average_score,
        max_score=detail.max_score,
    )


def run_directory_analysis(
    directory: Path,
    *,
    recursive: bool,
    interval: int | None,
    scorer: ImageScorer | None = None,
    directory_label: str | None = None,
    log_model: bool = True,
) -> DirectoryScoreResult:
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
    if log_model:
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

    result = DirectoryScoreResult(
        directory=directory_label or str(root),
        image_count=len(images),
        sampled_count=len(samples),
        successful_count=len(scores),
        failed_count=failed,
        interval=resolved_interval,
        average_score=_rounded_average(scores),
        max_score=max(scores),
    )
    logger.info("评分完成：成功 %d 张，失败 %d 张", len(scores), failed)
    return result


def run_independent_directory_scores(
    directory: Path,
    *,
    interval: int | None,
    scorer: ImageScorer | None = None,
    generated_at: datetime | None = None,
) -> IndependentScoreResult:
    directories = discover_image_directories(directory)
    root = directory.expanduser().resolve()
    if not directories:
        raise ScoringError("递归范围内没有直接包含 JPG 或 PNG 的合法子目录")

    active_scorer = scorer or LocalVisionScorer()
    logger.info("发现 %d 个可独立分析的子目录", len(directories))
    logger.info("评分模型：%s", active_scorer.model_version)
    results: list[DirectoryScoreResult] = []

    for index, child in enumerate(directories, start=1):
        label = child.relative_to(root).as_posix()
        logger.info("[%d/%d] 开始独立分析：%s", index, len(directories), label)
        try:
            result = run_directory_analysis(
                child,
                recursive=False,
                interval=interval,
                scorer=active_scorer,
                directory_label=label,
                log_model=False,
            )
        except SunsetScoreError as exc:
            logger.error(
                "[%d/%d] 子目录分析失败 %s：%s", index, len(directories), label, exc
            )
            result = DirectoryScoreResult(directory=label, error=str(exc))
        results.append(result)

    timestamp = generated_at or datetime.now().astimezone()
    draft = IndependentScoreResult(
        root_directory=str(root),
        generated_at=timestamp.isoformat(timespec="seconds"),
        model_version=active_scorer.model_version,
        report_path="",
        directories=tuple(results),
    )
    report_path = write_markdown_report(
        draft,
        root,
        filename_timestamp=timestamp.strftime("%Y%m%d-%H%M%S"),
    )
    final = replace(draft, report_path=str(report_path))
    logger.info("独立目录分析报告：%s", report_path)
    return final


def _rounded_average(scores: list[int]) -> float:
    value = Decimal(sum(scores)) / Decimal(len(scores))
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
