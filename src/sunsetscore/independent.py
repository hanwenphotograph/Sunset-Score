from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .discovery import discover_image_directories
from .errors import ScoringError, SunsetScoreError
from .inference.runner import LocalVisionScorer
from .inference.scheduling import resolve_inference_plan
from .log import logger
from .reporting import finalize_independent_result
from .results import DirectoryScoreResult, IndependentScoreResult
from .score_file import StoredDirectoryScore, read_score_file
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
    force: bool = False,
) -> IndependentScoreResult:
    directories = discover_image_directories(directory)
    root = directory.expanduser().resolve()
    if not directories:
        raise ScoringError("递归范围内没有直接包含 JPG 或 PNG 的合法子目录")

    cached_scores = {} if force else _read_cached_scores(directories, root)
    pending_count = len(directories) - len(cached_scores)
    active_scorer = scorer
    owned_scorer = pending_count > 0 and active_scorer is None
    if pending_count and active_scorer is None:
        active_scorer = LocalVisionScorer(cpu_infer=cpu_infer)
    try:
        logger.info(
            "发现 %d 个可独立分析的子目录，其中 %d 个将执行评分",
            len(directories),
            pending_count,
        )
        metadata_scorer = active_scorer if pending_count else None
        model_version, backend, device = _metadata(metadata_scorer, cached_scores)
        logger.info("评分模型：%s", model_version)
        logger.info("推理后端：%s，设备：%s", backend.upper(), device)
        if pending_count:
            assert active_scorer is not None
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
            cached_scores=cached_scores,
        )
        if pending_count:
            model_version, backend, device = _metadata(active_scorer, cached_scores)
        return finalize_independent_result(
            root,
            results,
            model_version=model_version,
            inference_backend=backend,
            inference_device=device,
            gpu_memory_limit=gpu_memory_limit,
            generated_at=generated_at,
            reuse_existing_report=pending_count == 0,
        )
    finally:
        if owned_scorer:
            assert isinstance(active_scorer, LocalVisionScorer)
            active_scorer.close()


def _read_cached_scores(
    directories: list[Path],
    root: Path,
) -> dict[Path, StoredDirectoryScore]:
    cached = {}
    for child in directories:
        label = child.relative_to(root).as_posix()
        stored = read_score_file(
            child,
            directory_label=label,
            recursive=False,
        )
        if stored is not None:
            cached[child] = stored
    return cached


def _score_directories(
    directories: list[Path],
    root: Path,
    *,
    interval: int | None,
    cpu_infer: bool,
    gpu_workers: int | None,
    gpu_memory_limit: float | None,
    scorer: ImageScorer | None,
    cached_scores: dict[Path, StoredDirectoryScore],
) -> list[DirectoryScoreResult]:
    results = []
    for index, child in enumerate(directories, start=1):
        label = child.relative_to(root).as_posix()
        stored = cached_scores.get(child)
        if stored is not None:
            logger.info(
                "[%d/%d] 使用已有评分：%s",
                index,
                len(directories),
                label,
            )
            results.append(stored.result)
            continue

        logger.info("[%d/%d] 开始独立分析：%s", index, len(directories), label)
        assert scorer is not None
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
                force=True,
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


def _metadata(
    scorer: ImageScorer | None,
    cached_scores: dict[Path, StoredDirectoryScore],
) -> tuple[str, str, str]:
    if scorer is not None:
        backend, device = _inference_metadata(scorer)
        return scorer.model_version, backend, device
    metadata = {
        (item.model_version, item.inference_backend, item.inference_device)
        for item in cached_scores.values()
    }
    if len(metadata) == 1:
        return next(iter(metadata))
    return "multiple cached models", "mixed", "mixed"
