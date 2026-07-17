"""Public API for SunsetScore."""

from .api import score_directories_independently, score_directory
from .results import IndependentScoreResult, ScoreResult

__all__ = [
    "IndependentScoreResult",
    "ScoreResult",
    "score_directories_independently",
    "score_directory",
]
__version__ = "0.6.0"
