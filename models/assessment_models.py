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

from typing import Annotated, List, Literal, Dict, Any
from pydantic import BaseModel, Field, BeforeValidator, ConfigDict


# Custom validator functions for reusable type coercion
def str_or_empty(v) -> str:
    """Convert any value to string or return empty string if None."""
    return "" if v is None else str(v).strip()


def non_empty_string_list(v) -> List[str]:
    """
    Ensure list contains only non-empty strings.

    Handles:
    - Non-list values (wraps in list)
    - None values (returns empty list)
    - Filters out empty/None items
    - Strips whitespace from all strings
    """
    if not isinstance(v, list):
        v = [v] if v else []
    return [str(item).strip() for item in v if item and str(item).strip()]


# Reusable annotated types using Pydantic v2 patterns
NonEmptyStr = Annotated[str, BeforeValidator(str_or_empty)]
StringList = Annotated[List[str], BeforeValidator(non_empty_string_list)]


class DetailedFeedback(BaseModel):
    """Detailed feedback on specific aspects of pronunciation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phonetic_accuracy: str = ""
    fluency: str = ""
    prosody: str = ""


class SpecificError(BaseModel):
    """Individual error with word-level feedback."""

    model_config = ConfigDict(str_strip_whitespace=True)

    word: NonEmptyStr
    issue: NonEmptyStr
    suggestion: NonEmptyStr
    severity: Literal["critical", "minor"] = "minor"


class AssessmentResult(BaseModel):
    """Complete assessment result from the pronunciation evaluation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    detailed_feedback: DetailedFeedback = Field(default_factory=DetailedFeedback)
    strengths: StringList = Field(default_factory=list)
    areas_for_improvement: StringList = Field(default_factory=list)
    specific_errors: List[SpecificError] = Field(default_factory=list)
    practice_suggestions: StringList = Field(default_factory=list)
    next_challenge_level: NonEmptyStr = ""
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
    return {
        "type": "object",
        "properties": {
            "detailed_feedback": {
                "type": "object",
                "properties": {
                    "phonetic_accuracy": {"type": "string"},
                    "fluency": {"type": "string"},
                    "prosody": {"type": "string"},
                },
            },
            "intelligibility_score": {
                "type": "string",
                "enum": ["excellent", "good", "needs_practice"],
            },
            "strengths": {"type": "array", "items": {"type": "string"}},
            "areas_for_improvement": {"type": "array", "items": {"type": "string"}},
            "specific_errors": {
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
            "practice_suggestions": {"type": "array", "items": {"type": "string"}},
            "next_challenge_level": {"type": "string"},
        },
        "required": [
            "intelligibility_score",
            "strengths",
            "areas_for_improvement",
            "specific_errors",
            "practice_suggestions",
            "next_challenge_level",
        ],
    }
