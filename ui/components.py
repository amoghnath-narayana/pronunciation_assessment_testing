"""UI components for displaying assessment results."""

import streamlit as st
from models.assessment_models import AssessmentResult
from constants import StreamlitMessageStyle
from utils import display_list_items_with_bullets


def render_strengths(strengths: list[str]) -> None:
    if strengths:
        st.subheader("Great Job")
        display_list_items_with_bullets(strengths, StreamlitMessageStyle.SUCCESS)


def render_specific_errors(errors: list) -> None:
    if not errors:
        return

    critical = [e for e in errors if e.severity == "critical"]
    minor = [e for e in errors if e.severity == "minor"]

    if critical:
        st.subheader("Focus On These")
        for e in critical:
            st.warning(f"**{e.word}**: {e.issue} → {e.suggestion}")

    if minor:
        if not critical:
            st.subheader("Focus On These")
        for e in minor:
            st.info(f"**{e.word}**: {e.issue} → {e.suggestion}")


def render_assessment(assessment_result: AssessmentResult) -> None:
    if not assessment_result:
        st.error("No assessment result available")
        return

    render_specific_errors(assessment_result.specific_errors)
    render_strengths(assessment_result.strengths)
