"""Utility functions for the Pronunciation Assessment Application."""

from __future__ import annotations

import streamlit as st


def create_practice_sentence_display_box(sentence_text: str) -> None:
    """
    Create a styled display box for the practice sentence.

    Args:
        sentence_text: The sentence to display
    """
    st.markdown(
        f"""
        <div style="
            border-radius: 24px;
            border: dashed 3px grey;
            padding: 24px;
            margin: 16px 0;
        ">
            <h3 style="text-align: center; color: #1f1f1f; font-size: 1.3em; line-height: 1.6; margin: 0;">
                {sentence_text}
            </h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
