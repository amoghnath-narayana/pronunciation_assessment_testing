"""Pydantic models for pronunciation assessment results."""

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class SpecificError(BaseModel):
    word: str
    issue: str
    suggestion: str
    severity: Literal["critical", "minor"] = "minor"


class AssessmentResult(BaseModel):
    specific_errors: List[SpecificError] = Field(default_factory=list)


def get_gemini_response_schema() -> Dict[str, Any]:
    """Return the JSON schema for Gemini API structured output.

    Gemini doesn't support $ref, so we define everything inline.
    """
    return {
        "type": "object",
        "properties": {
            "specific_errors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "word": {
                            "type": "string"
                        },
                        "issue": {
                            "type": "string"
                        },
                        "suggestion": {
                            "type": "string"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "minor"],
                        },
                    },
                    "required": ["word", "issue", "suggestion"],
                },
            },
        },
        "required": ["specific_errors"],
    }
