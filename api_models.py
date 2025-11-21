"""
API Request and Response Models.

These models define the contract between frontend and backend:
    - ErrorResponse: Standard error format
    - AzureAssessmentResponse: Assessment-only response (legacy)
    - AssessmentWithTTSResponse: Combined assessment + TTS response (optimized)
"""

from typing import Any

from pydantic import BaseModel, Field

from models.assessment_models import AzureAnalysisResult, OverallScores


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str
    message: str
    details: dict[str, Any] | None = None


class AzureAssessmentResponse(BaseModel):
    """
    Response for pronunciation assessment (without TTS).

    Used by: Legacy endpoints or when include_tts=False
    """

    summary_text: str = Field(description="Encouraging summary for the learner")
    overall_scores: OverallScores = Field(description="Azure pronunciation scores (0-100)")
    word_level_feedback: list = Field(default_factory=list, description="Word-level issues and suggestions")
    prosody_feedback: str | None = Field(default=None, description="Rhythm/intonation feedback")

    @classmethod
    def from_analysis_result(cls, result: AzureAnalysisResult) -> "AzureAssessmentResponse":
        """Create from AzureAnalysisResult."""
        return cls(
            summary_text=result.summary_text,
            overall_scores=result.overall_scores,
            word_level_feedback=[
                {"word": wf.word, "issue": wf.issue, "suggestion": wf.suggestion, "severity": wf.severity}
                for wf in result.word_level_feedback
            ],
            prosody_feedback=result.prosody_feedback,
        )


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
    overall_scores: OverallScores = Field(description="Azure pronunciation scores (0-100)")
    word_level_feedback: list = Field(default_factory=list, description="Word-level issues and suggestions")
    prosody_feedback: str | None = Field(default=None, description="Rhythm/intonation feedback")
    tts_audio_base64: str | None = Field(default=None, description="Base64-encoded WAV audio feedback")

    @classmethod
    def from_analysis_result(
        cls, result: AzureAnalysisResult, tts_audio_base64: str | None = None
    ) -> "AssessmentWithTTSResponse":
        """
        Create from AzureAnalysisResult with optional TTS audio.

        Args:
            result: The analysis result from Azure + Gemini pipeline
            tts_audio_base64: Optional base64-encoded WAV audio

        Returns:
            AssessmentWithTTSResponse: Combined response for frontend
        """
        return cls(
            summary_text=result.summary_text,
            overall_scores=result.overall_scores,
            word_level_feedback=[
                {"word": wf.word, "issue": wf.issue, "suggestion": wf.suggestion, "severity": wf.severity}
                for wf in result.word_level_feedback
            ],
            prosody_feedback=result.prosody_feedback,
            tts_audio_base64=tts_audio_base64,
        )
