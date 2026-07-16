from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """Aggregate scoring conclusion exposed to callers."""

    average_score: float
    max_score: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PhotoScore:
    """Internal model response for one sampled photo."""

    score: int
    reason: str
