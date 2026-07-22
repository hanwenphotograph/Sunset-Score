from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Protocol

from .discovery import resolve_input_image
from .inference.runner import LocalVisionScorer
from .inference.scheduling import log_inference_plan, resolve_inference_plan
from .log import logger
from .results import PhotoScore


class ImageScorer(Protocol):
    @property
    def model_version(self) -> str: ...

    def score(self, image: Path) -> PhotoScore: ...


def run_image_score(
    image: Path,
    *,
    cpu_infer: bool = False,
    gpu_workers: int | None = None,
    gpu_memory_limit: float | None = None,
    scorer: ImageScorer | None = None,
) -> PhotoScore:
    source = resolve_input_image(image)
    owned_scorer = LocalVisionScorer(cpu_infer=cpu_infer) if scorer is None else None
    active_scorer = owned_scorer if owned_scorer is not None else scorer
    assert active_scorer is not None
    try:
        _restore_acceleration(active_scorer)
        logger.info("评分模型：%s", active_scorer.model_version)
        backend, device = _inference_metadata(active_scorer)
        logger.info("推理后端：%s，设备：%s", backend.upper(), device)
        plan = resolve_inference_plan(
            active_scorer,
            1,
            gpu_workers=gpu_workers,
            gpu_memory_limit=gpu_memory_limit,
        )
        _configure_workers(active_scorer, plan.workers)
        log_inference_plan(plan)

        logger.info("[1/1] 正在评分：%s", source.name)
        started = perf_counter()
        result = active_scorer.score(source)
        logger.info(
            "[1/1] 得分 %d，耗时 %.2f 秒，理由：%s",
            result.score,
            perf_counter() - started,
            result.reason,
        )
        return result
    finally:
        if owned_scorer is not None:
            owned_scorer.close()


def _inference_metadata(scorer: object) -> tuple[str, str]:
    backend = getattr(scorer, "inference_backend", "unknown")
    device = getattr(scorer, "inference_device", "unknown")
    return str(backend), str(device)


def _configure_workers(scorer: object, workers: int) -> None:
    configure = getattr(scorer, "configure_workers", None)
    if callable(configure):
        configure(workers)


def _restore_acceleration(scorer: object) -> None:
    restore = getattr(scorer, "restore_acceleration", None)
    if callable(restore):
        restore()
