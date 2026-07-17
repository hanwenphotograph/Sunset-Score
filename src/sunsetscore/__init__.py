"""Public API for SunsetScore."""

from .api import score_directories_independently, score_directory
from .results import IndependentScoreResult, ScoreResult, SunsetRange
from .version import __version__

__all__ = [
    "IndependentScoreResult",
    "ScoreResult",
    "SunsetRange",
    "score_directories_independently",
    "score_directory",
]
