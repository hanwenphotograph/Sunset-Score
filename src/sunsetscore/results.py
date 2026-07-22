from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SunsetRange:
    """Inclusive sampled-photo range containing sunset-glow evidence."""

    start_photo: str
    end_photo: str

    def to_dict(self) -> dict[str, str]:
        return {
            "start_photo": self.start_photo,
            "end_photo": self.end_photo,
        }


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """Aggregate scoring conclusion exposed to callers."""

    average_score: float
    max_score: int
    has_sunset: bool = False
    sunset_ranges: tuple[SunsetRange, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "average_score": self.average_score,
            "max_score": self.max_score,
            "has_sunset": self.has_sunset,
            "sunset_ranges": [item.to_dict() for item in self.sunset_ranges],
        }


@dataclass(frozen=True, slots=True)
class DirectoryScoreResult:
    """Detailed aggregate for one independently analyzed directory."""

    directory: str
    image_count: int = 0
    sampled_count: int = 0
    successful_count: int = 0
    failed_count: int = 0
    interval: int | None = None
    inference_workers: int = 1
    average_score: float | None = None
    max_score: int | None = None
    has_sunset: bool | None = None
    sunset_ranges: tuple[SunsetRange, ...] = ()
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "directory": self.directory,
            "image_count": self.image_count,
            "sampled_count": self.sampled_count,
            "successful_count": self.successful_count,
            "failed_count": self.failed_count,
            "interval": self.interval,
            "inference_workers": self.inference_workers,
            "average_score": self.average_score,
            "max_score": self.max_score,
            "has_sunset": self.has_sunset,
            "sunset_ranges": [item.to_dict() for item in self.sunset_ranges],
            "error": self.error,
        }


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
    gpu_memory_limit_gib: float | None = None

    @property
    def successful_directory_count(self) -> int:
        return sum(item.succeeded for item in self.directories)

    @property
    def failed_directory_count(self) -> int:
        return len(self.directories) - self.successful_directory_count

    @property
    def inference_workers(self) -> int:
        return max((item.inference_workers for item in self.directories), default=1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_directory": self.root_directory,
            "generated_at": self.generated_at,
            "model_version": self.model_version,
            "inference_backend": self.inference_backend,
            "inference_device": self.inference_device,
            "inference_workers": self.inference_workers,
            "gpu_memory_limit_gib": self.gpu_memory_limit_gib,
            "report_path": self.report_path,
            "successful_directory_count": self.successful_directory_count,
            "failed_directory_count": self.failed_directory_count,
            "directories": [item.to_dict() for item in self.directories],
        }


@dataclass(frozen=True, slots=True)
class PhotoScore:
    """Scoring result for one photo."""

    score: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class SampleScore:
    """Successful model result tied to its sampled sequence position."""

    sample_index: int
    photo: str
    score: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_index": self.sample_index,
            "photo": self.photo,
            "score": self.score,
            "reason": self.reason,
        }
