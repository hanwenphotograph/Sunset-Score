from __future__ import annotations

from pathlib import Path
from threading import Lock
from time import sleep

import pytest

from sunsetscore.errors import ScoringError
from sunsetscore.inference.batch import score_image_batch
from sunsetscore.inference.scheduling import resolve_inference_plan
from sunsetscore.results import PhotoScore


class FakeGpuScorer:
    parallel_scoring_supported = True
    free_gpu_memory_mib = 15_009

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.lock = Lock()

    def score(self, image: Path) -> PhotoScore:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        sleep(0.02)
        with self.lock:
            self.active -= 1
        return PhotoScore(int(image.stem), image.name)


def test_automatic_plan_uses_four_workers_on_16gb_gpu() -> None:
    plan = resolve_inference_plan(
        FakeGpuScorer(),
        10,
        gpu_workers=None,
        gpu_memory_limit=None,
    )

    assert plan.workers == 4
    assert plan.memory_budget_mib == 13_985
    assert not plan.manually_limited


def test_manual_limits_are_combined() -> None:
    plan = resolve_inference_plan(
        FakeGpuScorer(),
        10,
        gpu_workers=6,
        gpu_memory_limit=6,
    )

    assert plan.workers == 2
    assert plan.memory_budget_mib == 6 * 1024
    assert plan.manually_limited


def test_unknown_gpu_memory_defaults_to_two_workers() -> None:
    scorer = FakeGpuScorer()
    scorer.free_gpu_memory_mib = None

    plan = resolve_inference_plan(
        scorer,
        10,
        gpu_workers=None,
        gpu_memory_limit=None,
    )

    assert plan.workers == 2
    assert plan.memory_budget_mib is None


def test_gpu_limits_are_rejected_for_serial_scorer() -> None:
    with pytest.raises(ScoringError, match="只能用于实际启用"):
        resolve_inference_plan(
            object(),
            10,
            gpu_workers=2,
            gpu_memory_limit=None,
        )


def test_parallel_batch_preserves_input_order_and_uses_workers(tmp_path) -> None:
    images = [tmp_path / f"{number}.jpg" for number in range(1, 7)]
    scorer = FakeGpuScorer()

    result = score_image_batch(images, tmp_path, scorer, workers=3)

    assert result.scores == (1, 2, 3, 4, 5, 6)
    assert result.failed_count == 0
    assert scorer.max_active == 3
