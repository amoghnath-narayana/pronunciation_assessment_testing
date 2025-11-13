"""Friendly pronunciation assessment for K1 and K2 learners."""

import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai

from config import APP_CONFIG, ButtonType, PageLayout
from practice_sentences import PRACTICE_SENTENCES
from utils import create_practice_sentence_display_box
from services.gemini_service import GeminiAssessmentService
from ui.components import render_assessment

# Configure Gemini API
genai.configure(api_key=APP_CONFIG.gemini_api_key)


def initialize_session_state() -> None:
    """Set the Streamlit state values used across the flow."""

    defaults = {
        "audio_data": None,
        "assessment_result": None,
        "practice_sentence": "",
        "sentence_index": 0,
        "trigger_scroll_to_assessment": False,
    }

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def get_practice_sentence(sentence_index: int = 0) -> str:
    """
    Get a practice sentence from the list.

    Args:
        sentence_index: Index of the sentence to retrieve

    Returns:
        str: The practice sentence at the given index
    """
    return PRACTICE_SENTENCES[sentence_index % len(PRACTICE_SENTENCES)]


def main() -> None:
    """
    Main application function.

    Returns:
        None
    """
    st.set_page_config(
        page_title="Pronunciation Coach",
        page_icon=":material/mic:",
        layout=PageLayout.WIDE.value,
    )

    st.markdown(
        """
        <style>
            section div.stMainBlockContainer {
                padding-left: 20rem !important;
                padding-right: 20rem !important;
            }

            @media (max-width: 768px) {
                section div.stMainBlockContainer {
                    padding-left: 1.5rem !important;
                    padding-right: 1.5rem !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Initialize session state
    initialize_session_state()

    # Initialize services
    assessment_service = GeminiAssessmentService(APP_CONFIG)

    mic_section_container = st.container()
    assessment_section_container = st.container()

    with mic_section_container:
        # Header and sentence refresh button
        header_col, button_col = st.columns([3, 1])

        with header_col:
            st.subheader("Practice Sentence")

        with button_col:
            st.write("")  # Empty space for alignment
            if st.button(
                ":material/refresh: New Sentence",
                type=ButtonType.PRIMARY.value,
                use_container_width=True,
            ):
                st.session_state.sentence_index = (
                    st.session_state.sentence_index + 1
                ) % len(PRACTICE_SENTENCES)
                st.session_state.assessment_result = None
                st.session_state.audio_data = None
                st.session_state.trigger_scroll_to_assessment = False
                st.rerun()

        # Get practice sentence from the list using current index
        current_practice_sentence = PRACTICE_SENTENCES[st.session_state.sentence_index]
        st.session_state.practice_sentence = current_practice_sentence

        # Display the sentence in a simple, clean box
        create_practice_sentence_display_box(current_practice_sentence)

        # Audio input widget (microphone recording)
        # Use sentence index for unique key to ensure recorder resets when sentence changes
        audio_input_key = f"audio_input_{st.session_state.sentence_index}"
        recorded_audio_value = st.audio_input(
            "Tap the mic to start speaking", key=audio_input_key
        )

        if recorded_audio_value is not None:
            recorded_audio_bytes = recorded_audio_value.read()
            st.session_state.audio_data = recorded_audio_bytes
            st.session_state.assessment_result = None
            st.session_state.trigger_scroll_to_assessment = False
        elif (
            st.session_state.audio_data is not None
            and st.session_state.get(audio_input_key) is None
        ):
            # Clear stored audio when the recorder value is removed by the user
            st.session_state.audio_data = None
            st.session_state.assessment_result = None
            st.session_state.trigger_scroll_to_assessment = False

        if st.session_state.audio_data:
            st.audio(
                st.session_state.audio_data, format=APP_CONFIG.recorded_audio_mime_type
            )

        assess_button_disabled = st.session_state.audio_data is None

        assess_button_clicked = st.button(
            "Assess Pronunciation",
            type=ButtonType.PRIMARY.value,
            use_container_width=True,
            disabled=assess_button_disabled,
        )

        if assess_button_clicked and st.session_state.audio_data:
            with st.spinner("Analyzing your pronunciation..."):
                pronunciation_assessment_result = assessment_service.assess_pronunciation(
                    st.session_state.audio_data,
                    st.session_state.practice_sentence,
                )
                st.session_state.assessment_result = pronunciation_assessment_result
                st.session_state.trigger_scroll_to_assessment = bool(
                    pronunciation_assessment_result
                )

    with assessment_section_container:
        st.divider()
        st.markdown('<div id="assessment-anchor"></div>', unsafe_allow_html=True)
        st.subheader("Assessment")

        assessment_result = st.session_state.assessment_result

        if assessment_result:
            render_assessment(assessment_result)

            if st.session_state.get("trigger_scroll_to_assessment"):
                components.html(
                    """
                    <script>
                    setTimeout(() => {
                        const parentWindow = window.parent;
                        if (!parentWindow) {
                            return;
                        }
                        const anchor = parentWindow.document.getElementById('assessment-anchor');
                        if (anchor && anchor.scrollIntoView) {
                            anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        }
                    }, 100);
                    </script>
                    """,
                    height=0,
                )
                st.session_state.trigger_scroll_to_assessment = False

        else:
            if st.session_state.audio_data:
                st.info("Tap Assess Pronunciation to see feedback here.")
            else:
                st.info("Record your reading with the mic above to receive feedback.")


if __name__ == "__main__":
    main()
