"""Public API for SunsetScore."""

from .api import score_directories_independently, score_directory, score_image
from .results import IndependentScoreResult, PhotoScore, ScoreResult, SunsetRange
from .version import __version__

__all__ = [
    "IndependentScoreResult",
    "PhotoScore",
    "ScoreResult",
    "SunsetRange",
    "score_directories_independently",
    "score_directory",
    "score_image",
    "__version__",
]
