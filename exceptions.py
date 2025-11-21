"""Custom exceptions for the Pronunciation Assessment API."""


class AssessmentError(Exception):
    """Base exception for assessment-related errors."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class AudioProcessingError(AssessmentError):
    """Exception raised when audio processing fails.

    This includes:
    - Empty audio data
    - Azure Speech API errors
    - Invalid audio format
    """

    pass


class InvalidAssessmentResponseError(AssessmentError):
    """Exception raised when Gemini returns invalid assessment data."""

    pass


class ConfigurationError(AssessmentError):
    """Exception raised when configuration is invalid.

    This includes:
    - Missing environment variables (SPEECH_KEY, SPEECH_REGION, etc.)
    - Invalid configuration values
    """

    pass
