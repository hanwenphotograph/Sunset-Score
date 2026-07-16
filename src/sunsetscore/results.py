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
class DirectoryScoreResult:
    """Detailed aggregate for one independently analyzed directory."""

    directory: str
    image_count: int = 0
    sampled_count: int = 0
    successful_count: int = 0
    failed_count: int = 0
    interval: int | None = None
    average_score: float | None = None
    max_score: int | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class IndependentScoreResult:
    """Results and report metadata for independent directory analysis."""

    root_directory: str
    generated_at: str
    model_version: str
    report_path: str
    directories: tuple[DirectoryScoreResult, ...]
    inference_backend: str = "unknown"
    inference_device: str = "unknown"

    @property
    def successful_directory_count(self) -> int:
        return sum(item.succeeded for item in self.directories)

    @property
    def failed_directory_count(self) -> int:
        return len(self.directories) - self.successful_directory_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_directory": self.root_directory,
            "generated_at": self.generated_at,
            "model_version": self.model_version,
            "inference_backend": self.inference_backend,
            "inference_device": self.inference_device,
            "report_path": self.report_path,
            "successful_directory_count": self.successful_directory_count,
            "failed_directory_count": self.failed_directory_count,
            "directories": [item.to_dict() for item in self.directories],
        }


@dataclass(frozen=True, slots=True)
class PhotoScore:
    """Internal model response for one sampled photo."""

    score: int
    reason: str
