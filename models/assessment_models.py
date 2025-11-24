"""Pydantic models for pronunciation assessment results."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class OverallScores(BaseModel):
    """Overall pronunciation scores from Azure (prosody removed for young learners)."""

    pronunciation: float = Field(
        default=0.0, description="Overall pronunciation score (0-100)"
    )
    accuracy: float = Field(
        default=0.0, description="Accuracy score for individual sounds (0-100)"
    )
    fluency: float = Field(default=0.0, description="Fluency and rhythm score (0-100)")
    completeness: float = Field(
        default=0.0, description="Completeness score for speaking all words (0-100)"
    )


class WordFeedback(BaseModel):
    """Word-level feedback with specific phoneme information."""

    word: str = Field(description="The word that has the pronunciation issue")
    letter: str = Field(
        description="The exact letter(s) in the word that need work (e.g., 'th', 'r', 'e')"
    )
    expected_sound: str = Field(
        description="The sound they should make (e.g., 'th', 'eh', 'ar')"
    )
    actual_sound: str = Field(
        description="The sound they actually made (e.g., 't', 'uh', 'aa')"
    )
    suggestion: str = Field(
        description="Child-friendly tip on how to make the correct sound"
    )
    severity: Literal["critical", "major", "minor"] = Field(
        default="minor",
        description="Severity level: 'critical' for wrong words, 'major' for serious pronunciation issues (score < 30), 'minor' for mild issues (score 30-50)",
    )


class AzureAnalysisResult(BaseModel):
    """Result from Gemini analysis of Azure pronunciation assessment."""

    summary_text: str = Field(
        description="Encouraging summary message for the learner (child-friendly, positive tone)"
    )
    overall_scores: OverallScores = Field(
        default_factory=OverallScores,
        description="Overall pronunciation scores from Azure assessment",
    )
    word_level_feedback: list[WordFeedback] = Field(
        default_factory=list,
        description="List of all problematic words with specific feedback (empty if perfect)",
    )


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
                },
                "required": [
                    "pronunciation",
                    "accuracy",
                    "fluency",
                    "completeness",
                ],
            },
            "word_level_feedback": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "word": {"type": "string"},
                        "letter": {"type": "string"},
                        "expected_sound": {"type": "string"},
                        "actual_sound": {"type": "string"},
                        "suggestion": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "major", "minor"],
                        },
                    },
                    "required": [
                        "word",
                        "letter",
                        "expected_sound",
                        "actual_sound",
                        "suggestion",
                        "severity",
                    ],
                },
            },
        },
        "required": ["summary_text", "overall_scores", "word_level_feedback"],
    }


# ============================================================================
# Azure Speech Service Response Models
# ============================================================================


class AzureOverallScores(BaseModel):
    """Overall pronunciation scores from NBest[0].PronunciationAssessment."""

    AccuracyScore: float = 0.0
    FluencyScore: float = 0.0
    CompletenessScore: float = 0.0
    PronScore: float = 0.0
    ProsodyScore: float = 0.0


class AzureWordScores(BaseModel):
    """Word-level pronunciation scores from Words[].PronunciationAssessment."""

    AccuracyScore: float = 0.0
    ErrorType: str = "None"


class AzurePhoneme(BaseModel):
    """Phoneme-level assessment data."""

    Phoneme: str
    PronunciationAssessment: dict[str, Any] = Field(default_factory=dict)
    NBestPhonemes: Optional[list[dict[str, Any]]] = None

    class Config:
        extra = "allow"


class AzureSyllable(BaseModel):
    """Syllable-level assessment data."""

    Syllable: str
    PronunciationAssessment: dict[str, Any] = Field(default_factory=dict)
    Grapheme: Optional[str] = None

    class Config:
        extra = "allow"


class AzureWordAssessment(BaseModel):
    """Word-level assessment from Azure Speech Service."""

    Word: str
    Offset: int = 0
    Duration: int = 0
    Confidence: float = 0.0
    PronunciationAssessment: AzureWordScores = Field(default_factory=AzureWordScores)
    Phonemes: list[AzurePhoneme] = Field(default_factory=list)
    Syllables: list[AzureSyllable] = Field(default_factory=list)

    class Config:
        extra = "allow"


class AzureNBestResult(BaseModel):
    """Single NBest result with scores and words."""

    Confidence: float = 0.9
    Lexical: str = ""
    ITN: str = ""
    MaskedITN: str = ""
    Display: str = ""
    PronunciationAssessment: AzureOverallScores = Field(
        default_factory=AzureOverallScores
    )
    Words: list[AzureWordAssessment] = Field(default_factory=list)

    class Config:
        extra = "allow"


class AzureRecognitionResult(BaseModel):
    """Complete Azure Speech Service recognition result."""

    RecognitionStatus: Literal[
        "Success", "NoMatch", "InitialSilenceTimeout", "BabbleTimeout", "Error"
    ] = "Success"
    DisplayText: str = ""
    NBest: list[AzureNBestResult] = Field(default_factory=list)

    @property
    def is_successful(self) -> bool:
        """Check if recognition was successful."""
        return self.RecognitionStatus == "Success" and len(self.NBest) > 0

    @property
    def pronunciation_scores(self) -> Optional[AzureOverallScores]:
        """Get overall pronunciation scores from NBest[0].PronunciationAssessment."""
        return self.NBest[0].PronunciationAssessment if self.is_successful else None

    @property
    def words(self) -> list[AzureWordAssessment]:
        """Get word-level assessments from best result."""
        return self.NBest[0].Words if self.is_successful else []

    class Config:
        extra = "allow"
