"""API request and response models for FastAPI endpoints."""

from typing import Any

from pydantic import BaseModel, Field

from constants import APIConfig
from models.assessment_models import AssessmentResult


# Request Models
class AssessmentRequest(BaseModel):
    """Request model for pronunciation assessment."""

    expected_text: str = Field(
        ...,
        description="The expected sentence text to assess pronunciation against",
        min_length=1,
    )


# Response Models
class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="healthy", description="Service health status")
    version: str = Field(default=APIConfig.VERSION, description="API version")


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error type or category")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional error details"
    )


class AssessmentResponse(BaseModel):
    """Response model for pronunciation assessment."""

    assessment: AssessmentResult = Field(
        ..., description="Assessment result with scores and feedback"
    )


class TTSResponse(BaseModel):
    """Response model for TTS generation (returned as audio stream)."""

    # This is actually returned as a StreamingResponse with audio/wav content-type
    # This model is just for documentation purposes
    pass


class AudioConfigResponse(BaseModel):
    """Audio configuration for frontend recording."""

    sample_rate: int = Field(..., description="Audio sample rate in Hz")
    channels: int = Field(
        ..., description="Number of audio channels (1=mono, 2=stereo)"
    )
    bit_depth: int = Field(..., description="Bit depth for audio samples")
    mime_type: str = Field(..., description="MIME type for audio files")
    vad_enabled: bool = Field(..., description="Whether VAD is enabled")
    vad_config: dict[str, Any] = Field(..., description="VAD configuration parameters")
