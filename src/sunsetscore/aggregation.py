from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from .results import SampleScore, SunsetRange


SUNSET_SCORE_THRESHOLD = 50
DETECTION_WINDOW_SIZE = 3
MIN_HIGH_SAMPLES = 2


@dataclass(frozen=True, slots=True)
class ScoreSummary:
    average_score: float
    max_score: int
    has_sunset: bool
    sunset_ranges: tuple[SunsetRange, ...]


def summarize_scores(
    samples: tuple[SampleScore, ...],
    *,
    sampled_count: int,
) -> ScoreSummary:
    if not samples:
        raise ValueError("samples must not be empty")
    selected = _qualifying_high_samples(samples, sampled_count=sampled_count)
    scores = [sample.score for sample in samples]
    return ScoreSummary(
        average_score=_rounded_average(scores),
        max_score=max(scores),
        has_sunset=bool(selected),
        sunset_ranges=_build_ranges(selected),
    )


def _qualifying_high_samples(
    samples: tuple[SampleScore, ...],
    *,
    sampled_count: int,
) -> dict[int, SampleScore]:
    high = {
        sample.sample_index: sample
        for sample in samples
        if sample.score >= SUNSET_SCORE_THRESHOLD
    }
    if sampled_count < DETECTION_WINDOW_SIZE:
        return high

    selected: dict[int, SampleScore] = {}
    last_start = sampled_count - DETECTION_WINDOW_SIZE + 1
    for start in range(1, last_start + 1):
        matches = [
            high[index]
            for index in range(start, start + DETECTION_WINDOW_SIZE)
            if index in high
        ]
        if len(matches) >= MIN_HIGH_SAMPLES:
            selected.update((sample.sample_index, sample) for sample in matches)
    return selected


def _build_ranges(samples: dict[int, SampleScore]) -> tuple[SunsetRange, ...]:
    ordered = sorted(samples.values(), key=lambda sample: sample.sample_index)
    if not ordered:
        return ()

    ranges: list[SunsetRange] = []
    start = previous = ordered[0]
    for current in ordered[1:]:
        if current.sample_index == previous.sample_index + 1:
            previous = current
            continue
        ranges.append(SunsetRange(start.photo, previous.photo))
        start = previous = current
    ranges.append(SunsetRange(start.photo, previous.photo))
    return tuple(ranges)


def _rounded_average(scores: list[int]) -> float:
    value = Decimal(sum(scores)) / Decimal(len(scores))
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
