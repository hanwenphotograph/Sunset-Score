from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Protocol

from .config import resolve_interval
from .discovery import discover_images, sample_images
from .errors import ScoringError
from .inference.batch import score_image_batch
from .inference.runner import LocalVisionScorer
from .inference.scheduling import log_inference_plan, resolve_inference_plan
from .log import logger
from .results import DirectoryScoreResult, PhotoScore, ScoreResult
from .score_file import read_score_file, write_score_file


class ImageScorer(Protocol):
    @property
    def model_version(self) -> str: ...

    @property
    def inference_backend(self) -> str: ...

    @property
    def inference_device(self) -> str: ...

    @property
    def parallel_scoring_supported(self) -> bool: ...

    @property
    def free_gpu_memory_mib(self) -> int | None: ...

    def score(self, image: Path) -> PhotoScore: ...


def run_directory_score(
    directory: Path,
    *,
    recursive: bool,
    interval: int | None,
    cpu_infer: bool = False,
    gpu_workers: int | None = None,
    gpu_memory_limit: float | None = None,
    scorer: ImageScorer | None = None,
    force: bool = False,
) -> ScoreResult:
    detail = run_directory_analysis(
        directory,
        recursive=recursive,
        interval=interval,
        cpu_infer=cpu_infer,
        gpu_workers=gpu_workers,
        gpu_memory_limit=gpu_memory_limit,
        scorer=scorer,
        force=force,
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
    cpu_infer: bool = False,
    gpu_workers: int | None = None,
    gpu_memory_limit: float | None = None,
    scorer: ImageScorer | None = None,
    directory_label: str | None = None,
    log_model: bool = True,
    force: bool = False,
) -> DirectoryScoreResult:
    images = discover_images(directory, recursive=recursive)
    root = directory.expanduser().resolve()
    label = directory_label or str(root)
    if not force:
        stored = read_score_file(
            root,
            directory_label=label,
            recursive=recursive,
        )
        if stored is not None:
            return stored.result
    if not images:
        raise ScoringError("输入目录中没有可评分的 JPG 或 PNG 照片")

    resolved_interval = resolve_interval(root, interval)
    samples = sample_images(images, resolved_interval)
    logger.info("扫描完成：共 %d 张照片，采样 %d 张", len(images), len(samples))
    logger.info(
        "采样间隔：%d，递归扫描：%s", resolved_interval, "是" if recursive else "否"
    )

    active_scorer = scorer or LocalVisionScorer(cpu_infer=cpu_infer)
    if log_model:
        logger.info("评分模型：%s", active_scorer.model_version)
        backend, device = _inference_metadata(active_scorer)
        logger.info("推理后端：%s，设备：%s", backend.upper(), device)
    plan = resolve_inference_plan(
        active_scorer,
        len(samples),
        gpu_workers=gpu_workers,
        gpu_memory_limit=gpu_memory_limit,
    )
    log_inference_plan(plan)
    batch = score_image_batch(samples, root, active_scorer, workers=plan.workers)
    scores = list(batch.scores)
    failed = batch.failed_count

    if not scores:
        raise ScoringError("所有采样照片均评分失败，无法生成运行结果")

    result = DirectoryScoreResult(
        directory=label,
        image_count=len(images),
        sampled_count=len(samples),
        successful_count=len(scores),
        failed_count=failed,
        interval=resolved_interval,
        inference_workers=plan.workers,
        average_score=_rounded_average(scores),
        max_score=max(scores),
    )
    logger.info("评分完成：成功 %d 张，失败 %d 张", len(scores), failed)
    backend, device = _inference_metadata(active_scorer)
    write_score_file(
        root,
        result,
        model_version=active_scorer.model_version,
        inference_backend=backend,
        inference_device=device,
        recursive=recursive,
    )
    return result


def _rounded_average(scores: list[int]) -> float:
    value = Decimal(sum(scores)) / Decimal(len(scores))
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _inference_metadata(scorer: ImageScorer) -> tuple[str, str]:
    backend = getattr(scorer, "inference_backend", "unknown")
    device = getattr(scorer, "inference_device", "unknown")
    return str(backend), str(device)
