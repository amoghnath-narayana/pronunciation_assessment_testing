"""Friendly pronunciation assessment for K1 and K2 learners."""

import streamlit as st
import streamlit.components.v1 as components
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
    """Create a detailed prompt tailored for Indian English learners."""

    return (
        "You are listening to a short reading from a young Indian child (K1/K2, ages 5-7).\n"
        "This child is a native speaker of an Indian language learning English as an additional language.\n\n"
        f'Expected sentence: "{expected_sentence_text}"\n\n'
        "CRITICAL CONTEXT FOR ASSESSMENT:\n"
        "- This is an Indian English speaker - expect and ACCEPT natural Indian English features.\n"
        "- ONLY flag pronunciation issues that significantly impact INTELLIGIBILITY for a general English listener.\n"
        "- DO NOT flag these acceptable Indian English variations:\n"
        "  * Retroflex consonants (t, d, r sounds)\n"
        "  * Slight vowel quality differences (cat sounds like ket, cup sounds like cap)\n"
        "  * Different stress patterns if meaning remains clear\n"
        "  * Less vowel reduction in unstressed syllables\n\n"
        "PRIORITY ASSESSMENT AREAS (flag ONLY if clearly wrong):\n"
        "1. V/W Distinction: Does child distinguish V and W sounds? (van should not sound like wan)\n"
        "2. Dental Fricatives TH: TH sounds in think and this - flag if they become T or D sounds\n"
        "3. S/SH Distinction: S sound in sip versus SH sound in ship - flag if confused\n"
        "4. Aspiration: Initial P, T, K sounds should have air puff (pin should not sound like bin)\n\n"
        "FEEDBACK PHILOSOPHY:\n"
        "- Be warm, simple, and encouraging.\n"
        "- Maximum 1-2 corrections per assessment (focus on highest impact only).\n"
        "- If pronunciation is intelligible despite accent, praise it.\n"
        "- Parents should understand without linguistic jargon.\n\n"
        "EXAMPLE 1 - Acceptable Indian English:\n"
        "Audio: Child says I have a cat with slight retroflex sounds and cat sounds like ket.\n"
        "Assessment: {\n"
        '  "intelligibility_score": "excellent",\n'
        '  "strengths": ["Clear words", "Nice steady pace", "Good confidence"],\n'
        '  "areas_for_improvement": [],\n'
        '  "specific_errors": [],\n'
        '  "practice_suggestions": ["Great job! Try a longer sentence next"]\n'
        "}\n"
        "Explanation: Retroflex sounds and vowel shifts are acceptable - do not flag.\n\n"
        "EXAMPLE 2 - Critical Error:\n"
        "Audio: Child says I have a wan instead of I have a van.\n"
        "Assessment: {\n"
        '  "intelligibility_score": "needs_practice",\n'
        '  "strengths": ["Clear voice", "Good try"],\n'
        '  "specific_errors": [{"word": "van", "issue": "Sounds like wan", "suggestion": "Put your top teeth gently on your lower lip and buzz vvv-an", "severity": "critical"}],\n'
        '  "areas_for_improvement": ["Practice the V sound with your teeth on your lip"]\n'
        "}\n\n"
        "Respond with JSON containing:\n"
        '- "detailed_feedback": {"phonetic_accuracy": <1 short sentence>, "fluency": <1 short sentence>, "prosody": <1 short sentence>}\n'
        '- "strengths": [<list of 2-3 specific things child did well, 5-7 words each>]\n'
        '- "areas_for_improvement": [<max 2 high-impact suggestions in simple language>]\n'
        '- "specific_errors": [{"word": <word>, "issue": <what happened>, "suggestion": <how to improve>, "severity": <"critical" or "minor">}]\n'
        '- "practice_suggestions": [<2-3 fun, actionable activities>]\n'
        '- "next_challenge_level": <brief suggestion>\n'
        '- "intelligibility_score": <"excellent", "good", or "needs_practice">\n\n'
        "Do not add text outside the JSON."
    )


DEFAULT_DETAILED_FEEDBACK = {"phonetic_accuracy": "", "fluency": "", "prosody": ""}


def _parse_assessment_response(response_text: str) -> Dict[str, Any]:
    """Parse the JSON object from the model response text."""

    json_start_index = response_text.find("{")
    json_end_index = response_text.rfind("}")

    if json_start_index == -1 or json_end_index <= json_start_index:
        raise ValueError("Response does not contain a JSON object.")

    json_payload = response_text[json_start_index : json_end_index + 1]
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
        "next_challenge_level": "",
        "intelligibility_score": "",
    }

    detailed_feedback = raw_result.get("detailed_feedback", {})

    if isinstance(detailed_feedback, dict):
        normalized_result["detailed_feedback"] = {
            "phonetic_accuracy": _ensure_string(
                detailed_feedback.get("phonetic_accuracy")
            ),
            "fluency": _ensure_string(detailed_feedback.get("fluency")),
            "prosody": _ensure_string(detailed_feedback.get("prosody")),
        }

    def _string_list(values: Any) -> list:
        if isinstance(values, list):
            return [_ensure_string(item) for item in values if _ensure_string(item)]
        coerced_value = _ensure_string(values)
        return [coerced_value] if coerced_value else []

    normalized_result["strengths"] = _string_list(raw_result.get("strengths", []))
    normalized_result["areas_for_improvement"] = _string_list(
        raw_result.get("areas_for_improvement", [])
    )
    normalized_result["practice_suggestions"] = _string_list(
        raw_result.get("practice_suggestions", [])
    )

    specific_errors_raw = raw_result.get("specific_errors", [])

    if not isinstance(specific_errors_raw, list):
        specific_errors_raw = [specific_errors_raw]

    for error_entry in specific_errors_raw:
        if isinstance(error_entry, dict):
            normalized_result["specific_errors"].append(
                {
                    "word": _ensure_string(error_entry.get("word")),
                    "issue": _ensure_string(error_entry.get("issue")),
                    "suggestion": _ensure_string(error_entry.get("suggestion")),
                    "severity": _ensure_string(error_entry.get("severity", "minor")),
                }
            )

    normalized_result["next_challenge_level"] = _ensure_string(
        raw_result.get("next_challenge_level", "")
    )
    normalized_result["intelligibility_score"] = _ensure_string(
        raw_result.get("intelligibility_score", "")
    )

    return normalized_result


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


def assess_pronunciation(
    audio_data_bytes: bytes, expected_sentence_text: str
) -> Optional[Dict]:
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
            response_mime_type=base_generation.response_mime_type,
        )

        model = genai.GenerativeModel(
            model_name=APP_CONFIG.model_name,
            system_instruction=SYSTEM_PROMPT,
            generation_config=generation_config,
        )

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=APP_CONFIG.temp_file_extension
        ) as temp_audio_file:
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
                response_mime_type=assessment_generation.response_mime_type,
            ),
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
    """Display the assessment with severity-aware formatting."""
    if not assessment_result_data:
        st.error("No assessment result available")
        return

    # Display intelligibility score prominently
    intelligibility = assessment_result_data.get("intelligibility_score", "")
    if intelligibility:
        score_label = {
            "excellent": "Excellent",
            "good": "Good",
            "needs_practice": "Needs Practice",
        }
        display_text = score_label.get(intelligibility.lower(), intelligibility.title())
        st.success(f"**Intelligibility: {display_text}**")

    # Always show strengths first
    student_strengths = assessment_result_data.get("strengths", [])
    if student_strengths:
        st.subheader("Great Job")
        display_list_items_with_bullets(
            student_strengths, StreamlitMessageStyle.SUCCESS
        )

    # Separate critical and minor errors
    specific_word_errors = assessment_result_data.get("specific_errors", [])
    if specific_word_errors:
        critical_errors = [
            e for e in specific_word_errors if e.get("severity") == "critical"
        ]
        minor_errors = [e for e in specific_word_errors if e.get("severity") == "minor"]

        if critical_errors:
            st.subheader("Focus On These")
            for word_error in critical_errors:
                error_word = word_error.get("word", "Word")
                error_issue = word_error.get("issue", "")
                error_suggestion = word_error.get("suggestion", "")
                st.warning(f"**{error_word}**: {error_issue} → {error_suggestion}")

        if minor_errors:
            with st.expander("Additional Tips (Optional)"):
                for word_error in minor_errors:
                    error_word = word_error.get("word", "Word")
                    error_issue = word_error.get("issue", "")
                    error_suggestion = word_error.get("suggestion", "")
                    st.info(f"**{error_word}**: {error_issue} → {error_suggestion}")

    # Show improvement areas
    improvement_areas = assessment_result_data.get("areas_for_improvement", [])
    if improvement_areas:
        st.subheader("Try These Next")
        display_list_items_with_bullets(improvement_areas, StreamlitMessageStyle.INFO)


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
                pronunciation_assessment_result = assess_pronunciation(
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
            format_assessment_result(assessment_result)

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
