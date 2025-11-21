"""API request and response models for FastAPI endpoints."""

from typing import Any

from pydantic import BaseModel, Field

from models.assessment_models import AzureAnalysisResult, OverallScores


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    message: str
    details: dict[str, Any] | None = None


class AzureAssessmentResponse(BaseModel):
    """Response for pronunciation assessment."""

    summary_text: str = Field(description="Encouraging summary")
    overall_scores: OverallScores = Field(description="Azure pronunciation scores")
    word_level_feedback: list = Field(default_factory=list, description="Word-level feedback")
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
