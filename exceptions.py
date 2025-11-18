"""Custom exceptions for the Pronunciation Assessment API."""


class AssessmentError(Exception):
    """Base exception for assessment-related errors."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class AudioUploadError(AssessmentError):
    """Exception raised when audio upload to Gemini API fails."""

    pass


class AudioProcessingError(AssessmentError):
    """Exception raised when audio processing fails."""

    pass


class InvalidAssessmentResponseError(AssessmentError):
    """Exception raised when Gemini returns invalid assessment data."""

    pass


class TTSGenerationError(AssessmentError):
    """Exception raised when TTS generation fails."""

    pass


class ConfigurationError(AssessmentError):
    """Exception raised when configuration is invalid."""

    pass
