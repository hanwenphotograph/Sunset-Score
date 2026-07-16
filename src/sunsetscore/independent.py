from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .discovery import discover_image_directories
from .errors import ScoringError, SunsetScoreError
from .inference.runner import LocalVisionScorer
from .inference.scheduling import resolve_inference_plan
from .log import logger
from .reporting import write_markdown_report
from .results import DirectoryScoreResult, IndependentScoreResult
from .service import ImageScorer, _inference_metadata, run_directory_analysis


def run_independent_directory_scores(
    directory: Path,
    *,
    interval: int | None,
    cpu_infer: bool = False,
    gpu_workers: int | None = None,
    gpu_memory_limit: float | None = None,
    scorer: ImageScorer | None = None,
    generated_at: datetime | None = None,
) -> IndependentScoreResult:
    directories = discover_image_directories(directory)
    root = directory.expanduser().resolve()
    if not directories:
        raise ScoringError("递归范围内没有直接包含 JPG 或 PNG 的合法子目录")

    active_scorer = scorer or LocalVisionScorer(cpu_infer=cpu_infer)
    logger.info("发现 %d 个可独立分析的子目录", len(directories))
    logger.info("评分模型：%s", active_scorer.model_version)
    backend, device = _inference_metadata(active_scorer)
    logger.info("推理后端：%s，设备：%s", backend.upper(), device)
    resolve_inference_plan(
        active_scorer,
        1,
        gpu_workers=gpu_workers,
        gpu_memory_limit=gpu_memory_limit,
    )
    results = _score_directories(
        directories,
        root,
        interval=interval,
        cpu_infer=cpu_infer,
        gpu_workers=gpu_workers,
        gpu_memory_limit=gpu_memory_limit,
        scorer=active_scorer,
    )
    return _write_result(
        root,
        results,
        active_scorer,
        gpu_memory_limit=gpu_memory_limit,
        generated_at=generated_at,
    )


def _score_directories(
    directories: list[Path],
    root: Path,
    *,
    interval: int | None,
    cpu_infer: bool,
    gpu_workers: int | None,
    gpu_memory_limit: float | None,
    scorer: ImageScorer,
) -> list[DirectoryScoreResult]:
    results = []
    for index, child in enumerate(directories, start=1):
        label = child.relative_to(root).as_posix()
        logger.info("[%d/%d] 开始独立分析：%s", index, len(directories), label)
        try:
            result = run_directory_analysis(
                child,
                recursive=False,
                interval=interval,
                cpu_infer=cpu_infer,
                gpu_workers=gpu_workers,
                gpu_memory_limit=gpu_memory_limit,
                scorer=scorer,
                directory_label=label,
                log_model=False,
            )
        except SunsetScoreError as exc:
            logger.error(
                "[%d/%d] 子目录分析失败 %s：%s",
                index,
                len(directories),
                label,
                exc,
            )
            result = DirectoryScoreResult(directory=label, error=str(exc))
        results.append(result)
    return results


def _write_result(
    root: Path,
    results: list[DirectoryScoreResult],
    scorer: ImageScorer,
    *,
    gpu_memory_limit: float | None,
    generated_at: datetime | None,
) -> IndependentScoreResult:
    timestamp = generated_at or datetime.now().astimezone()
    backend, device = _inference_metadata(scorer)
    draft = IndependentScoreResult(
        root_directory=str(root),
        generated_at=timestamp.isoformat(timespec="seconds"),
        model_version=scorer.model_version,
        report_path="",
        directories=tuple(results),
        inference_backend=backend,
        inference_device=device,
        gpu_memory_limit_gib=gpu_memory_limit,
    )
    report_path = write_markdown_report(
        draft,
        root,
        filename_timestamp=timestamp.strftime("%Y%m%d-%H%M%S"),
    )
    logger.info("独立目录分析报告：%s", report_path)
    return replace(draft, report_path=str(report_path))
