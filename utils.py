"""
Utility functions for the Pronunciation Assessment Application
"""

from __future__ import annotations

from typing import Union

import streamlit as st

from config import StreamlitMessageStyle


def display_list_items_with_bullets(
    items_list: list,
    container_type: Union[StreamlitMessageStyle, str] = StreamlitMessageStyle.INFO,
) -> None:
    """
    Display a list of items with bullet points using a Streamlit container style.

    Args:
        items_list: List of items to display
        container_type: StreamlitMessageStyle enum value (or string) indicating the container
    """
    if isinstance(container_type, str):
        try:
            container_style = StreamlitMessageStyle(container_type)
        except ValueError:
            container_style = StreamlitMessageStyle.WRITE
    else:
        container_style = container_type

    containers = {
        StreamlitMessageStyle.INFO: st.info,
        StreamlitMessageStyle.SUCCESS: st.success,
        StreamlitMessageStyle.WARNING: st.warning,
        StreamlitMessageStyle.WRITE: st.write,
    }
    render = containers.get(container_style, st.write)

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
