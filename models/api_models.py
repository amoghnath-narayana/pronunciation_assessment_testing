"""
API Request and Response Models.

These models define the contract between frontend and backend:
    - ErrorResponse: Standard error format
    - AssessmentWithTTSResponse: Assessment response with scores and feedback
"""

from typing import Any

from pydantic import BaseModel, Field

from models.assessment_models import AzureAnalysisResult, OverallScores

__all__ = [
    "ErrorResponse",
    "AssessmentResponse",
]


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str
    message: str
    details: dict[str, Any] | None = None


class AssessmentResponse(BaseModel):
    """
    Assessment response with scores and feedback.

    Used by: POST /api/v1/assess
    """

    summary_text: str = Field(description="Encouraging summary for the learner")
    overall_scores: OverallScores = Field(
        description="Azure pronunciation scores (0-100)"
    )
    word_level_feedback: list = Field(
        default_factory=list, description="Word-level issues and suggestions"
    )

    @classmethod
    def from_analysis_result(
        cls, result: AzureAnalysisResult
    ) -> "AssessmentResponse":
        """Create from AzureAnalysisResult using Pydantic's model_validate."""
        return cls(
            summary_text=result.summary_text,
            overall_scores=result.overall_scores,
            word_level_feedback=[wf.model_dump() for wf in result.word_level_feedback],
        )
