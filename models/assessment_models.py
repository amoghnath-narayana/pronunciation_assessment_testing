"""Pydantic models for pronunciation assessment results."""

from typing import List, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class SpecificError(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    word: str
    issue: str
    suggestion: str
    severity: Literal["critical", "minor"] = "minor"


class AssessmentResult(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    strengths: List[str] = Field(default_factory=list)
    areas_for_improvement: List[str] = Field(default_factory=list)
    specific_errors: List[SpecificError] = Field(default_factory=list)
    practice_suggestions: List[str] = Field(default_factory=list)
    next_challenge_level: str = ""
    intelligibility_score: Literal["excellent", "good", "needs_practice", ""] = ""
    speaking_speed: Literal["slow", "normal", "fast", ""] = ""


def get_gemini_response_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "intelligibility_score": {
                "type": "string",
                "enum": ["excellent", "good", "needs_practice"],
            },
            "speaking_speed": {
                "type": "string",
                "enum": ["slow", "normal", "fast"],
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
