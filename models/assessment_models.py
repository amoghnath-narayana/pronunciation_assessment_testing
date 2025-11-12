"""
Pydantic models for pronunciation assessment results.

These models provide automatic validation, type safety, and JSON parsing
for assessment data returned by the AI model.

Uses Pydantic v2 features:
- Annotated types with BeforeValidator for clean type coercion
- ConfigDict for model-level configuration
- Reusable validator functions
- JSON schema generation for Gemini's response_schema parameter
"""

from typing import List, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DetailedFeedback(BaseModel):
    """Detailed feedback on specific aspects of pronunciation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phonetic_accuracy: str = ""
    fluency: str = ""
    prosody: str = ""


class SpecificError(BaseModel):
    """Individual error with word-level feedback."""

    model_config = ConfigDict(str_strip_whitespace=True)

    word: str
    issue: str
    suggestion: str
    severity: Literal["critical", "minor"] = "minor"


class AssessmentResult(BaseModel):
    """Complete assessment result from the pronunciation evaluation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    detailed_feedback: DetailedFeedback = Field(default_factory=DetailedFeedback)
    strengths: List[str] = Field(default_factory=list)
    areas_for_improvement: List[str] = Field(default_factory=list)
    specific_errors: List[SpecificError] = Field(default_factory=list)
    practice_suggestions: List[str] = Field(default_factory=list)
    next_challenge_level: str = ""
    intelligibility_score: Literal["excellent", "good", "needs_practice", ""] = ""


def get_gemini_response_schema() -> Dict[str, Any]:
    """
    Generate Gemini API response_schema from Pydantic model.

    This schema can be passed to Gemini's generation_config to enforce
    structured JSON output, eliminating the need for:
    - Manual JSON extraction
    - OUTPUT SCHEMA in system prompt
    - "Return JSON only" instructions

    Returns:
        Dict containing JSON schema compatible with Gemini API
    """
    return AssessmentResult.model_json_schema()
