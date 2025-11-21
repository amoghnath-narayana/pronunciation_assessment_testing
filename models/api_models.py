"""
API Request and Response Models.

These models define the contract between frontend and backend:
    - ErrorResponse: Standard error format
    - AssessmentWithTTSResponse: Combined assessment + TTS response
"""

from typing import Any

from pydantic import BaseModel, Field

from models.assessment_models import AzureAnalysisResult, OverallScores

__all__ = [
    "ErrorResponse",
    "AssessmentWithTTSResponse",
]


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str
    message: str
    details: dict[str, Any] | None = None


class AssessmentWithTTSResponse(BaseModel):
    """
    Combined assessment + TTS response (optimized single-request flow).

    This response model supports the optimized pipeline where:
        - Single API call returns both scores and TTS audio
        - TTS audio is base64-encoded WAV for easy frontend playback
        - Eliminates duplicate Azure+Gemini calls (~1.5-2.5s saved)

    Used by: POST /api/v1/assess (with include_tts=True)
    """

    summary_text: str = Field(description="Encouraging summary for the learner")
    overall_scores: OverallScores = Field(
        description="Azure pronunciation scores (0-100)"
    )
    word_level_feedback: list = Field(
        default_factory=list, description="Word-level issues and suggestions"
    )
    tts_audio_base64: str | None = Field(
        default=None, description="Base64-encoded WAV audio feedback"
    )

    @classmethod
    def from_analysis_result(
        cls, result: AzureAnalysisResult, tts_audio_base64: str | None = None
    ) -> "AssessmentWithTTSResponse":
        """Create from AzureAnalysisResult using Pydantic's model_validate."""
        return cls(
            summary_text=result.summary_text,
            overall_scores=result.overall_scores,
            word_level_feedback=[wf.model_dump() for wf in result.word_level_feedback],
            tts_audio_base64=tts_audio_base64,
        )
