from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from ..log import logger
from ..results import DirectoryScoreResult, IndependentScoreResult
from .markdown import latest_markdown_report, write_markdown_report


def finalize_independent_result(
    root: Path,
    results: list[DirectoryScoreResult],
    *,
    model_version: str,
    inference_backend: str,
    inference_device: str,
    gpu_memory_limit: float | None,
    generated_at: datetime | None,
    reuse_existing_report: bool,
) -> IndependentScoreResult:
    timestamp = generated_at or datetime.now().astimezone()
    draft = IndependentScoreResult(
        root_directory=str(root),
        generated_at=timestamp.isoformat(timespec="seconds"),
        model_version=model_version,
        report_path="",
        directories=tuple(results),
        inference_backend=inference_backend,
        inference_device=inference_device,
        gpu_memory_limit_gib=gpu_memory_limit,
    )
    existing_report = latest_markdown_report(root) if reuse_existing_report else None
    if existing_report is not None:
        logger.info("复用独立目录分析报告：%s", existing_report)
        return replace(draft, report_path=str(existing_report))

    report_path = write_markdown_report(
        draft,
        root,
        filename_timestamp=timestamp.strftime("%Y%m%d-%H%M%S"),
    )
    logger.info("独立目录分析报告：%s", report_path)
    return replace(draft, report_path=str(report_path))
