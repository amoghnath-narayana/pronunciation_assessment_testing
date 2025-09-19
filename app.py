"""Friendly pronunciation assessment for K1 and K2 learners."""

import streamlit as st
import google.generativeai as genai
import os
import tempfile
import json
from json import JSONDecodeError
from typing import Any, Dict, Optional

from config import APP_CONFIG, ButtonType, PageLayout, StreamlitMessageStyle

from constants import SYSTEM_PROMPT
from practice_sentences import PRACTICE_SENTENCES
from utils import display_list_items_with_bullets, create_practice_sentence_display_box

# Configure Gemini API
genai.configure(api_key=APP_CONFIG.gemini_api_key)


def build_assessment_prompt(expected_sentence_text: str) -> str:
    """Create a simple prompt tailored for early learners and their helpers."""

    return (
        "You are listening to a short reading from a young child (K1/K2).\n"
        "Be warm, clear, and encouraging. Use only simple words any parent can understand.\n\n"
        f'The child tried to say: "{expected_sentence_text}"\n\n'
        "Share the result as one JSON object with these keys:\n"
        '- "detailed_feedback": dictionary with keys "phonetic_accuracy", "fluency", "prosody". Use 1 short sentence each.\n'
        '- "strengths": list of quick cheer sentences (max 5-7 words).\n'
        '- "areas_for_improvement": list of gentle reminders written like "Try saying ____".\n'
        '- "specific_errors": list of dictionaries with keys "word", "issue", "suggestion". Use short phrases.\n'
        '- "practice_suggestions": list of playful practice ideas, each under 12 words.\n'
        '- "next_challenge_level": short phrase such as "Try a longer sentence".\n\n'
        "Do not add extra text outside the JSON."
    )


DEFAULT_DETAILED_FEEDBACK = {
    "phonetic_accuracy": "",
    "fluency": "",
    "prosody": ""
}


def _parse_assessment_response(response_text: str) -> Dict[str, Any]:
    """Parse the JSON object from the model response text."""

    json_start_index = response_text.find('{')
    json_end_index = response_text.rfind('}')

    if json_start_index == -1 or json_end_index <= json_start_index:
        raise ValueError("Response does not contain a JSON object.")

    json_payload = response_text[json_start_index:json_end_index + 1]
    return json.loads(json_payload)


def _ensure_string(value: Any) -> str:
    """Coerce values returned by the model to clean strings."""

    if value is None:
        return ""
    return str(value).strip()


def _normalize_assessment(raw_result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the assessment dictionary to ensure expected structure."""

    normalized_result: Dict[str, Any] = {
        "detailed_feedback": DEFAULT_DETAILED_FEEDBACK.copy(),
        "strengths": [],
        "areas_for_improvement": [],
        "specific_errors": [],
        "practice_suggestions": [],
        "next_challenge_level": ""
    }

    detailed_feedback = raw_result.get("detailed_feedback", {})

    if isinstance(detailed_feedback, dict):
        normalized_result["detailed_feedback"] = {
            "phonetic_accuracy": _ensure_string(detailed_feedback.get("phonetic_accuracy")),
            "fluency": _ensure_string(detailed_feedback.get("fluency")),
            "prosody": _ensure_string(detailed_feedback.get("prosody"))
        }

    def _string_list(values: Any) -> list:
        if isinstance(values, list):
            return [_ensure_string(item) for item in values if _ensure_string(item)]
        coerced_value = _ensure_string(values)
        return [coerced_value] if coerced_value else []

    normalized_result["strengths"] = _string_list(raw_result.get("strengths", []))
    normalized_result["areas_for_improvement"] = _string_list(raw_result.get("areas_for_improvement", []))
    normalized_result["practice_suggestions"] = _string_list(raw_result.get("practice_suggestions", []))

    specific_errors_raw = raw_result.get("specific_errors", [])

    if not isinstance(specific_errors_raw, list):
        specific_errors_raw = [specific_errors_raw]

    for error_entry in specific_errors_raw:
        if isinstance(error_entry, dict):
            normalized_result["specific_errors"].append({
                "word": _ensure_string(error_entry.get("word")),
                "issue": _ensure_string(error_entry.get("issue")),
                "suggestion": _ensure_string(error_entry.get("suggestion"))
            })

    normalized_result["next_challenge_level"] = _ensure_string(raw_result.get("next_challenge_level", ""))

    return normalized_result


def initialize_session_state() -> None:
    """Set the Streamlit state values used across the flow."""

    defaults = {
        "audio_data": None,
        "assessment_result": None,
        "practice_sentence": "",
        "sentence_index": 0
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


def assess_pronunciation(audio_data_bytes: bytes, expected_sentence_text: str) -> Optional[Dict]:
    """
    Send audio to Gemini API for pronunciation assessment.
    
    Args:
        audio_data_bytes: Audio data in bytes format
        expected_sentence_text: The text the student should pronounce
    
    Returns:
        Optional[Dict]: Assessment result dictionary or None if error
    """
    temp_audio_file_path: Optional[str] = None

    try:
        base_generation = APP_CONFIG.base_generation

        generation_config = genai.GenerationConfig(
            temperature=base_generation.temperature,
            max_output_tokens=base_generation.max_output_tokens,
            response_mime_type=base_generation.response_mime_type
        )

        model = genai.GenerativeModel(
            model_name=APP_CONFIG.model_name,
            system_instruction=SYSTEM_PROMPT,
            generation_config=generation_config
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=APP_CONFIG.temp_file_extension) as temp_audio_file:
            temp_audio_file.write(audio_data_bytes)
            temp_audio_file_path = temp_audio_file.name

        uploaded_audio_file = genai.upload_file(temp_audio_file_path)

        assessment_prompt = build_assessment_prompt(expected_sentence_text)

        assessment_generation = APP_CONFIG.assessment_generation

        api_response = model.generate_content(

            [assessment_prompt, uploaded_audio_file],

            generation_config=genai.GenerationConfig(
                temperature=assessment_generation.temperature,
                max_output_tokens=assessment_generation.max_output_tokens,
                response_mime_type=assessment_generation.response_mime_type
            )

        )

        parsed_assessment_result = _parse_assessment_response(api_response.text)
        return _normalize_assessment(parsed_assessment_result)

    except (JSONDecodeError, ValueError) as parsing_error:
        st.error(f"Unable to parse assessment response: {parsing_error}")
        return None
    except Exception as error:
        st.error(f"Error during assessment: {str(error)}")
        return None
    finally:
        if temp_audio_file_path and os.path.exists(temp_audio_file_path):
            os.unlink(temp_audio_file_path)


def format_assessment_result(assessment_result_data: Dict) -> None:
    """Display the assessment highlights without detailed sections."""
    if not assessment_result_data:
        st.error("No assessment result available")
        return
    
    improvement_areas = assessment_result_data.get("areas_for_improvement", [])
    if improvement_areas:
        st.subheader("Try These Next")
        display_list_items_with_bullets(improvement_areas, StreamlitMessageStyle.INFO)

    specific_word_errors = assessment_result_data.get("specific_errors", [])
    if specific_word_errors:
        st.subheader("Words to Practice")
        for word_error in specific_word_errors:
            error_word = word_error.get('word', 'Word')
            error_issue = word_error.get('issue', '')
            error_suggestion = word_error.get('suggestion', '')
            st.warning(f"**{error_word}**: {error_issue} :material/arrow_forward: {error_suggestion}")

    student_strengths = assessment_result_data.get("strengths", [])
    if student_strengths:
        st.subheader("Bright Spots")
        display_list_items_with_bullets(student_strengths, StreamlitMessageStyle.SUCCESS)

def main() -> None:
    """
    Main application function.
    
    Returns:
        None
    """
    st.set_page_config(page_title="Pronunciation Coach",page_icon=":material/mic:",layout=PageLayout.WIDE.value)

    # Initialize session state
    initialize_session_state()

    mic_section_container = st.container()
    assessment_section_container = st.container()

    with mic_section_container:
        # Header and sentence refresh button
        header_col, button_col = st.columns([3, 1])

        with header_col:
            st.subheader("Practice Sentence")

        with button_col:

            st.write("")  # Empty space for alignment
            if st.button(":material/refresh: New Sentence",type=ButtonType.PRIMARY.value,use_container_width=True):
                st.session_state.sentence_index = (st.session_state.sentence_index + 1) % len(PRACTICE_SENTENCES)
                st.session_state.assessment_result = None
                st.session_state.audio_data = None
                st.rerun()

        # Get practice sentence from the list using current index
        current_practice_sentence = PRACTICE_SENTENCES[st.session_state.sentence_index]
        st.session_state.practice_sentence = current_practice_sentence

        # Display the sentence in a simple, clean box
        create_practice_sentence_display_box(current_practice_sentence)

        # Audio input widget (microphone recording)
        # Use sentence index for unique key to ensure recorder resets when sentence changes
        audio_input_key = f"audio_input_{st.session_state.sentence_index}"
        recorded_audio_value = st.audio_input("Tap the mic to start speaking", key=audio_input_key)

        if recorded_audio_value is not None:
            recorded_audio_bytes = recorded_audio_value.read()
            st.session_state.audio_data = recorded_audio_bytes
            st.session_state.assessment_result = None

        if st.session_state.audio_data:
            st.audio(st.session_state.audio_data, format=APP_CONFIG.recorded_audio_mime_type)

        assess_button_disabled = st.session_state.audio_data is None

        assess_button_clicked = st.button(
            "Assess Pronunciation",
            type=ButtonType.PRIMARY.value,
            use_container_width=True,
            disabled=assess_button_disabled
        )

        if assess_button_clicked and st.session_state.audio_data:
            with st.spinner("Analyzing your pronunciation..."):
                pronunciation_assessment_result = assess_pronunciation(
                    st.session_state.audio_data,
                    st.session_state.practice_sentence,
                )
                st.session_state.assessment_result = pronunciation_assessment_result

    with assessment_section_container:
        st.divider()
        st.subheader("Assessment")

        assessment_result = st.session_state.assessment_result

        if assessment_result:
            format_assessment_result(assessment_result)
            next_challenge_level = assessment_result.get("next_challenge_level")

            if next_challenge_level:
                st.info(f"Next challenge: {next_challenge_level}")
        else:
            if st.session_state.audio_data:
                st.info("Tap Assess Pronunciation to see feedback here.")
            else:
                st.info("Record your reading with the mic above to receive feedback.")


if __name__ == "__main__":
    main()
