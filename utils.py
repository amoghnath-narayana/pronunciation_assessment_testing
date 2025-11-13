"""
Utility functions for the Pronunciation Assessment Application
"""

from __future__ import annotations

import streamlit as st

from constants import StreamlitMessageStyle


def display_list_items_with_bullets(
    items_list: list[str],
    container_type: StreamlitMessageStyle = StreamlitMessageStyle.INFO,
) -> None:
    """
    Display a list of items with bullet points using a Streamlit container style.

    Args:
        items_list: List of items to display
        container_type: StreamlitMessageStyle enum value indicating the container style
    """
    render = getattr(st, container_type.value)
    for item in items_list:
        render(f"• {item}")


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
