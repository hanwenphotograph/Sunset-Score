"""Public API for SunsetScore."""

from .api import score_directory
from .results import ScoreResult

__all__ = ["ScoreResult", "score_directory"]
__version__ = "0.1.0"
