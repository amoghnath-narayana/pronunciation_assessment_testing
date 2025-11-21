"""Custom exceptions for the Pronunciation Assessment API."""


class AssessmentError(Exception):
    """Base exception for all assessment-related errors.
    
    Attributes:
        message: Human-readable error message
        details: Optional dictionary with additional error context
        error_type: Type of error for categorization
    """

    def __init__(
        self,
        message: str,
        details: dict | None = None,
        error_type: str = "general",
    ):
        self.message = message
        self.details = details or {}
        self.error_type = error_type
        super().__init__(self.message)


# Convenience aliases for common error types
class AudioProcessingError(AssessmentError):
    """Audio processing errors (empty data, format issues, Azure API failures)."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, details, error_type="audio_processing")


class InvalidAssessmentResponseError(AssessmentError):
    """Invalid response from Gemini analysis."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, details, error_type="invalid_response")
