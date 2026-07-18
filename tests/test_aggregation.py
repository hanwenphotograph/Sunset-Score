from __future__ import annotations

from sunsetscore.aggregation import summarize_scores
from sunsetscore.results import SampleScore, SunsetRange


def _samples(*scores: int) -> tuple[SampleScore, ...]:
    return tuple(
        SampleScore(
            sample_index=index,
            photo=f"photo{index}.jpg",
            score=score,
            reason="模拟理由",
        )
        for index, score in enumerate(scores, start=1)
    )


def test_isolated_high_score_is_not_sunset() -> None:
    result = summarize_scores(_samples(1, 4, 1), sampled_count=3)

    assert result.has_sunset is False
    assert result.sunset_ranges == ()


def test_two_high_scores_in_three_samples_are_sunset() -> None:
    result = summarize_scores(_samples(4, 1, 4), sampled_count=3)

    assert result.has_sunset is True
    assert result.sunset_ranges == (
        SunsetRange("photo1.jpg", "photo1.jpg"),
        SunsetRange("photo3.jpg", "photo3.jpg"),
    )


def test_contiguous_ranges_exclude_unqualified_high_scores() -> None:
    result = summarize_scores(
        _samples(1, 3, 4, 5, 1, 1, 4, 1, 1),
        sampled_count=9,
    )

    assert result.has_sunset is True
    assert result.sunset_ranges == (
        SunsetRange("photo2.jpg", "photo4.jpg"),
    )


def test_short_sequence_uses_any_high_score() -> None:
    result = summarize_scores(_samples(1, 3), sampled_count=2)

    assert result.has_sunset is True
    assert result.sunset_ranges == (
        SunsetRange("photo2.jpg", "photo2.jpg"),
    )


def test_failed_sample_keeps_successful_neighbors_separate() -> None:
    samples = (
        SampleScore(1, "first.jpg", 4, "模拟理由"),
        SampleScore(3, "third.jpg", 4, "模拟理由"),
    )

    result = summarize_scores(samples, sampled_count=3)

    assert result.has_sunset is True
    assert result.sunset_ranges == (
        SunsetRange("first.jpg", "first.jpg"),
        SunsetRange("third.jpg", "third.jpg"),
    )
