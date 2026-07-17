"""Application-specific exceptions."""


class SunsetScoreError(Exception):
    """Base class for expected user-facing failures."""


class ConfigError(SunsetScoreError):
    """Raised when local configuration is invalid."""


class InputError(SunsetScoreError):
    """Raised when the input directory cannot be processed."""


class ScoringError(SunsetScoreError):
    """Raised when a run cannot produce a valid aggregate score."""


class ReportError(SunsetScoreError):
    """Raised when an analysis report cannot be generated."""


class ScoreFileError(SunsetScoreError):
    """Raised when a completed score cannot be persisted."""


class AutopackError(SunsetScoreError):
    """Raised when sunset photos cannot be copied into the result directory."""


class RuntimeInstallError(SunsetScoreError):
    """Raised when the local inference runtime cannot be prepared."""


class PhotoProcessingError(SunsetScoreError):
    """Raised when one sampled photo cannot be scored."""


class InferenceError(PhotoProcessingError):
    """Raised when model inference or response parsing fails."""


class ImagePreparationError(PhotoProcessingError):
    """Raised when an input image cannot be decoded or normalized."""
