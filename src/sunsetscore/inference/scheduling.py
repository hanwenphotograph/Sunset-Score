from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

from ..errors import ScoringError
from ..log import logger
from .settings import (
    GPU_FIT_TARGET_MIB,
    GPU_SLOT_MEMORY_MIB,
    MAX_GPU_SERVER_SLOTS,
    UNKNOWN_MEMORY_GPU_SLOTS,
)


MINIMUM_GPU_MEMORY_LIMIT_GIB = 3.0


class SchedulableScorer(Protocol):
    @property
    def parallel_scoring_supported(self) -> bool: ...

    @property
    def free_gpu_memory_mib(self) -> int | None: ...


@dataclass(frozen=True, slots=True)
class InferencePlan:
    workers: int
    memory_budget_mib: int | None
    manually_limited: bool

    @property
    def memory_budget_gib(self) -> float | None:
        if self.memory_budget_mib is None:
            return None
        return self.memory_budget_mib / 1024


def log_inference_plan(plan: InferencePlan) -> None:
    mode = "手动限制" if plan.manually_limited else "自动"
    if plan.memory_budget_gib is None:
        logger.info("推理服务槽位：%d（%s，显存容量未知）", plan.workers, mode)
        return
    logger.info(
        "推理服务槽位：%d（%s，显存调度预算 %.2f GiB）",
        plan.workers,
        mode,
        plan.memory_budget_gib,
    )


def resolve_inference_plan(
    scorer: object,
    sample_count: int,
    *,
    gpu_workers: int | None,
    gpu_memory_limit: float | None,
) -> InferencePlan:
    _validate_limits(gpu_workers, gpu_memory_limit)
    parallel = bool(getattr(scorer, "parallel_scoring_supported", False))
    if not parallel:
        if gpu_workers is not None or gpu_memory_limit is not None:
            fallback_active = bool(
                getattr(scorer, "accelerator_fallback_active", False)
            )
            if not fallback_active:
                raise ScoringError("GPU 并发限制只能用于实际启用的 GPU 推理后端")
            logger.warning("GPU 回退仍处于活动状态，本目录忽略 GPU 并发限制")
        return InferencePlan(1, None, False)

    free_memory = _optional_positive_int(getattr(scorer, "free_gpu_memory_mib", None))
    memory_budget = _memory_budget(free_memory, gpu_memory_limit)
    requested_workers = min(gpu_workers or MAX_GPU_SERVER_SLOTS, MAX_GPU_SERVER_SLOTS)
    if memory_budget is None:
        memory_workers = (
            requested_workers
            if gpu_memory_limit is not None
            else UNKNOWN_MEMORY_GPU_SLOTS
        )
    else:
        memory_workers = max(1, memory_budget // GPU_SLOT_MEMORY_MIB)
    workers = max(1, min(sample_count, requested_workers, memory_workers))
    return InferencePlan(
        workers=workers,
        memory_budget_mib=memory_budget,
        manually_limited=gpu_workers is not None or gpu_memory_limit is not None,
    )


def _validate_limits(
    gpu_workers: int | None,
    gpu_memory_limit: float | None,
) -> None:
    if gpu_workers is not None and (
        not isinstance(gpu_workers, int)
        or isinstance(gpu_workers, bool)
        or gpu_workers < 1
        or gpu_workers > MAX_GPU_SERVER_SLOTS
    ):
        raise ScoringError(
            f"GPU 推理服务槽位数必须是 1 到 {MAX_GPU_SERVER_SLOTS} 的整数"
        )
    if gpu_memory_limit is None:
        return
    if (
        not isinstance(gpu_memory_limit, (int, float))
        or isinstance(gpu_memory_limit, bool)
        or not math.isfinite(gpu_memory_limit)
        or (gpu_memory_limit < MINIMUM_GPU_MEMORY_LIMIT_GIB)
    ):
        raise ScoringError(
            f"GPU 显存预算必须大于等于 {MINIMUM_GPU_MEMORY_LIMIT_GIB:g} GiB"
        )


def _memory_budget(
    free_memory_mib: int | None,
    requested_limit_gib: float | None,
) -> int | None:
    detected_budget = None
    if free_memory_mib is not None:
        detected_budget = max(0, free_memory_mib - GPU_FIT_TARGET_MIB)
    requested_budget = (
        int(requested_limit_gib * 1024) if requested_limit_gib is not None else None
    )
    budgets = [item for item in (detected_budget, requested_budget) if item is not None]
    return min(budgets) if budgets else None


def _optional_positive_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None
