"""Pydantic models for pronunciation assessment results."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class OverallScores(BaseModel):
    """Overall pronunciation scores from Azure."""

    pronunciation: float = 0.0
    accuracy: float = 0.0
    fluency: float = 0.0
    completeness: float = 0.0
    prosody: float = 0.0


class WordFeedback(BaseModel):
    """Word-level feedback."""

    word: str
    issue: str
    suggestion: str
    severity: Literal["critical", "minor"] = "minor"


class AzureAnalysisResult(BaseModel):
    """Result from Gemini analysis of Azure pronunciation assessment."""

    summary_text: str = Field(description="Encouraging summary for the learner")
    overall_scores: OverallScores = Field(default_factory=OverallScores)
    word_level_feedback: list[WordFeedback] = Field(default_factory=list)
    prosody_feedback: str | None = None

    @property
    def specific_errors(self) -> list[WordFeedback]:
        """Alias for TTS compatibility."""
        return self.word_level_feedback


def get_azure_analysis_response_schema() -> dict[str, Any]:
    """JSON schema for Gemini structured output."""
    return {
        "type": "object",
        "properties": {
            "summary_text": {"type": "string"},
            "overall_scores": {
                "type": "object",
                "properties": {
                    "pronunciation": {"type": "number"},
                    "accuracy": {"type": "number"},
                    "fluency": {"type": "number"},
                    "completeness": {"type": "number"},
                    "prosody": {"type": "number"},
                },
                "required": [
                    "pronunciation",
                    "accuracy",
                    "fluency",
                    "completeness",
                    "prosody",
                ],
            },
            "word_level_feedback": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "word": {"type": "string"},
                        "issue": {"type": "string"},
                        "suggestion": {"type": "string"},
                        "severity": {"type": "string", "enum": ["critical", "minor"]},
                    },
                    "required": ["word", "issue", "suggestion", "severity"],
                },
            },
            "prosody_feedback": {"type": ["string", "null"]},
        },
        "required": ["summary_text", "overall_scores", "word_level_feedback"],
    }
