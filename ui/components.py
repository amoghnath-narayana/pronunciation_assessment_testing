"""
UI components for displaying assessment results.

Contains reusable components for rendering assessment data in the Streamlit interface.
"""

import streamlit as st

from models.assessment_models import AssessmentResult
from config import StreamlitMessageStyle
from utils import display_list_items_with_bullets


def render_intelligibility_score(score: str) -> None:
    """
    Display the intelligibility score prominently.

    Args:
        score: The intelligibility score (excellent, good, needs_practice)
    """
    if score:
        score_label = {
            "excellent": "Excellent",
            "good": "Good",
            "needs_practice": "Needs Practice",
        }
        display_text = score_label.get(score.lower(), score.title())
        st.success(f"**Intelligibility: {display_text}**")


def render_strengths(strengths: list[str]) -> None:
    """
    Display the student's strengths.

    Args:
        strengths: List of strength descriptions
    """
    if strengths:
        st.subheader("Great Job")
        display_list_items_with_bullets(strengths, StreamlitMessageStyle.SUCCESS)


def render_specific_errors(errors: list) -> None:
    """
    Display specific errors separated by severity (critical vs minor).

    Args:
        errors: List of SpecificError objects
    """
    if not errors:
        return

    # Separate critical and minor errors
    critical_errors = [e for e in errors if e.severity == "critical"]
    minor_errors = [e for e in errors if e.severity == "minor"]

    # Display critical errors prominently
    if critical_errors:
        st.subheader("Focus On These")
        for error in critical_errors:
            st.warning(f"**{error.word}**: {error.issue} → {error.suggestion}")

    # Display minor errors in an expandable section
    if minor_errors:
        with st.expander("Additional Tips (Optional)"):
            for error in minor_errors:
                st.info(f"**{error.word}**: {error.issue} → {error.suggestion}")


def render_improvement_areas(areas: list[str]) -> None:
    """
    Display areas for improvement.

    Args:
        areas: List of improvement suggestions
    """
    if areas:
        st.subheader("Try These Next")
        display_list_items_with_bullets(areas, StreamlitMessageStyle.INFO)


def render_assessment(assessment_result: AssessmentResult) -> None:
    """
    Display the complete assessment with severity-aware formatting.

    Args:
        assessment_result: The complete assessment result to display
    """
    if not assessment_result:
        st.error("No assessment result available")
        return

    # Display intelligibility score
    render_intelligibility_score(assessment_result.intelligibility_score)

    # Show specific errors (critical and minor)
    render_specific_errors(assessment_result.specific_errors)

    # Always show strengths first
    render_strengths(assessment_result.strengths)

    # Show improvement areas
    render_improvement_areas(assessment_result.areas_for_improvement)
