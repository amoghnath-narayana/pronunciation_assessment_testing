"""
Pronunciation Assessment Application
Using Gemini 2.5 Pro for K-12 Indian Students
"""

import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
import tempfile
from typing import Dict
import json

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# System prompt for pronunciation assessment
SYSTEM_PROMPT = """
English Pronunciation Assessment for Indian Students

## Role & Context
You are an AI English pronunciation tutor designed for Indian students. Your primary function is to assess and improve English pronunciation through reading exercises.

## Core Responsibilities

### 1. Content Focus
**Practice content focuses on:**
- Commonly mispronounced sounds by Indian English speakers
- Clear articulation and natural English rhythm
- Building confidence through practice

### 2. Pronunciation Analysis Framework

**Primary Assessment Parameters (Yes/No/NA Scoring):**

#### Phonetic Accuracy
- **Consonant Clarity:** Clear articulation of consonants (especially TH, V, W, R)
- **Vowel Precision:** Correct vowel sounds (avoiding substitutions)
- **Sound Substitution:** Absence of common L1 interference

#### Fluency Markers
- **Word Stress:** Correct primary stress placement
- **Rhythm Pattern:** Natural English rhythm and timing
- **Linking Sounds:** Appropriate connected speech

#### Prosodic Features
- **Intonation:** Appropriate rise and fall patterns
- **Pace Control:** Neither too fast nor too slow
- **Pause Placement:** Natural breathing and thought pauses

### 3. Common Indian English Pronunciation Challenges to Monitor

**Consonant Issues:**
- Final consonant clusters reduction
- R pronunciation (retroflex vs. approximant)

**Vowel Issues:**
- Schwa vowel in unstressed syllables
- Short vs. long vowel distinctions
- Diphthong pronunciation

**Stress and Rhythm:**
- Syllable-timed vs. stress-timed rhythm
- Word stress placement
- Sentence stress patterns

### 4. Feedback Structure

**For Each Assessment, Provide:**

1. **Overall Score Summary:**
    - Phonetic Accuracy: Yes/No/NA
    - Fluency: Yes/No/NA
    - Prosody: Yes/No/NA

2. **Specific Feedback:**
    - Correctly pronounced elements (positive reinforcement)
    - Specific errors with examples
    - Target sounds to practice

3. **Improvement Suggestions:**
    - Specific drills for identified issues
    - Mouth positioning guidance
    - Practice words/sentences

4. **Encouragement:**
    - Grade-appropriate motivational feedback
    - Progress acknowledgment
    - Next steps guidance

### 5. Scoring Guidelines

**YES:** Clear, accurate pronunciation meeting target standards
**NO:** Pronunciation errors that affect intelligibility or accuracy
**NA:** Parameter not applicable to the given content or unclear audio

### 6. Cultural Sensitivity Guidelines

- Acknowledge Indian English as a valid variety while teaching Standard American/British features
- Be encouraging and patient with L1 interference patterns
- Use familiar cultural references when providing examples
- Avoid negative comparisons with native speaker models

### 7. Interaction Flow

1. **Introduction:** "Hi! I'm here to help improve your English pronunciation."

2. **Practice:** "Let's practice with this sentence: [practice content]"

3. **Analysis:**
    - Listen to student's recording
    - Analyze pronunciation accuracy
    - Provide structured feedback

4. **Follow-up:** Suggest targeted exercises based on identified areas

## Example Assessment Template

**Student Input:** [Audio recording of reading]

**Assessment:**
- Phonetic Accuracy: [Yes/No/NA] - [Specific feedback]
- Fluency: [Yes/No/NA] - [Specific feedback]
- Prosody: [Yes/No/NA] - [Specific feedback]

**Strengths:** [List 2-3 positive elements]
**Areas for Improvement:** [List 1-2 specific issues]
**Practice Suggestion:** [Targeted exercise]
**Next Challenge:** [Appropriate progression]

---

Remember: Your goal is to build confidence while improving accuracy. Every student's journey is unique, and progress should be celebrated at every step.
"""

# Practice sentences for pronunciation
PRACTICE_SENTENCES = [
    "The weather is beautiful today with clear blue skies.",
    "Thank you very much for your thoughtful assistance.",
    "We should always think before we speak.",
    "Technology has revolutionized the way we communicate.",
    "This village festival brings everyone together.",
    "I practice writing every evening after dinner.",
    "The scientific method involves careful observation.",
    "Cultural diversity enriches our understanding.",
    "Environmental conservation is everyone's responsibility.",
    "Critical thinking skills are essential for success.",
    "The three brothers went through the thick forest.",
    "She sells seashells by the seashore.",
    "Whether the weather is warm or cold.",
    "The quick brown fox jumps over the lazy dog.",
    "Practice makes perfect with persistent effort."
]


def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if 'audio_data' not in st.session_state:
        st.session_state.audio_data = None
    if 'assessment_result' not in st.session_state:
        st.session_state.assessment_result = None
    if 'practice_sentence' not in st.session_state:
        st.session_state.practice_sentence = ""
    if 'recording_status' not in st.session_state:
        st.session_state.recording_status = "ready"


def get_practice_sentence(index: int = 0) -> str:
    """Get a practice sentence"""
    return PRACTICE_SENTENCES[index % len(PRACTICE_SENTENCES)]


def assess_pronunciation(audio_data: bytes, expected_text: str) -> Dict:
    """
    Send audio to Gemini API for pronunciation assessment
    """
    try:
        # Initialize the Gemini model (using latest version)
        generation_config = genai.GenerationConfig(
            temperature=1.0,
            max_output_tokens=8192,
            response_mime_type="text/plain"
        )

        model = genai.GenerativeModel(
            model_name="gemini-2.5-pro",
            system_instruction=SYSTEM_PROMPT,
            generation_config=generation_config
        )

        # Create a temporary file for the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_file.write(audio_data)
            tmp_file_path = tmp_file.name

        # Upload the audio file to Gemini
        audio_file = genai.upload_file(tmp_file_path)

        # Create the prompt
        prompt = f"""
        Expected Text: "{expected_text}"

        Please analyze the student's pronunciation of the above text from the audio recording.

        Provide your assessment in the following JSON format:
        {{
            "overall_scores": {{
                "phonetic_accuracy": "Yes/No/NA",
                "fluency": "Yes/No/NA",
                "prosody": "Yes/No/NA"
            }},
            "detailed_feedback": {{
                "phonetic_accuracy_details": "Specific feedback on consonants, vowels, sound substitutions",
                "fluency_details": "Feedback on word stress, rhythm, linking sounds",
                "prosody_details": "Feedback on intonation, pace, pauses"
            }},
            "strengths": ["strength1", "strength2", "strength3"],
            "areas_for_improvement": ["area1", "area2"],
            "specific_errors": [
                {{"word": "example_word", "issue": "pronunciation issue", "suggestion": "how to fix"}}
            ],
            "practice_suggestions": ["suggestion1", "suggestion2"],
            "encouragement": "Motivational message",
            "next_challenge": "Suggested next practice sentence"
        }}
        """

        # Generate response with thinking enabled
        response = model.generate_content(
            [prompt, audio_file],
            generation_config=genai.GenerationConfig(
                temperature=0.6,
                max_output_tokens=8192,
                response_mime_type="text/plain"
            )
        )

        # Clean up temporary file
        os.unlink(tmp_file_path)

        # Parse the JSON response
        try:
            # Extract JSON from the response
            response_text = response.text
            # Find JSON content between curly braces
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            json_str = response_text[start_idx:end_idx]
            result = json.loads(json_str)
        except:
            # If JSON parsing fails, create a structured response
            result = {
                "overall_scores": {
                    "phonetic_accuracy": "NA",
                    "fluency": "NA",
                    "prosody": "NA"
                },
                "detailed_feedback": {
                    "phonetic_accuracy_details": response.text,
                    "fluency_details": "",
                    "prosody_details": ""
                },
                "strengths": ["Recording received"],
                "areas_for_improvement": ["Unable to parse detailed assessment"],
                "specific_errors": [],
                "practice_suggestions": ["Please try recording again"],
                "encouragement": "Keep practicing!",
                "next_challenge": expected_text
            }

        return result

    except Exception as e:
        st.error(f"Error during assessment: {str(e)}")
        return None


def format_assessment_result(result: Dict) -> None:
    """Format and display the assessment result in a user-friendly way"""
    if not result:
        st.error("No assessment result available")
        return

    # Display overall scores
    st.subheader(":material/analytics: Assessment Results")

    cols = st.columns(3)
    score_icons = {"Yes": ":material/check_circle:", "No": ":material/cancel:", "NA": ":material/warning:"}

    with cols[0]:
        score = result["overall_scores"]["phonetic_accuracy"]
        st.info(f"**Pronunciation**\n{score_icons[score]} {score}")

    with cols[1]:
        score = result["overall_scores"]["fluency"]
        st.info(f"**Fluency**\n{score_icons[score]} {score}")

    with cols[2]:
        score = result["overall_scores"]["prosody"]
        st.info(f"**Rhythm & Tone**\n{score_icons[score]} {score}")

    # Display strengths
    if result.get("strengths"):
        st.subheader(":material/star: What You Did Well")
        for strength in result["strengths"]:
            st.success(f"• {strength}")

    # Display areas for improvement
    if result.get("areas_for_improvement"):
        st.subheader(":material/lightbulb: Areas to Work On")
        for area in result["areas_for_improvement"]:
            st.info(f"• {area}")

    # Display specific errors
    if result.get("specific_errors") and len(result["specific_errors"]) > 0:
        st.subheader(":material/search: Specific Words to Practice")
        for error in result["specific_errors"]:
            st.warning(f"**{error.get('word', 'Word')}**: {error.get('issue', '')} :material/arrow_forward: {error.get('suggestion', '')}")

    # Display practice suggestions
    if result.get("practice_suggestions"):
        st.subheader(":material/edit_note: Practice Tips")
        for suggestion in result["practice_suggestions"]:
            st.write(f"• {suggestion}")

    # Display encouragement and next steps
    if result.get("encouragement") or result.get("next_challenge"):
        st.markdown("---")
        if result.get("encouragement"):
            st.markdown(f"**:material/fitness_center: {result['encouragement']}**")
        if result.get("next_challenge"):
            st.info(f"**Next Practice:** {result['next_challenge']}")


def main():
    """Main application function"""
    st.set_page_config(
        page_title="Pronunciation Assessment",
        page_icon=":material/mic:",
        layout="wide"
    )

    # Initialize session state
    initialize_session_state()

    # App header
    st.title(":material/mic: English Pronunciation Assessment")
    st.markdown("*Practice and improve your English pronunciation*")
    st.markdown("---")

    # Main content area
    col1, col2 = st.columns([1, 1])

    # Get random sentence index (or cycle through them)
    import random
    if 'sentence_index' not in st.session_state:
        st.session_state.sentence_index = 0
    sentence_index = st.session_state.sentence_index

    with col1:
        st.subheader("Practice Sentence")

        # Get and display practice sentence
        st.session_state.practice_sentence = get_practice_sentence(sentence_index)

        # Display the sentence in a simple, clean box
        st.markdown(
            f"""
            <div style="
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 24px;
                margin: 16px 0;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            ">
                <h3 style="text-align: center; color: #1f1f1f; font-size: 1.3em; line-height: 1.6; margin: 0;">
                    {st.session_state.practice_sentence}
                </h3>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Add button to get new sentence
        if st.button(":material/refresh: Get New Sentence", use_container_width=True):
            st.session_state.sentence_index = (st.session_state.sentence_index + 1) % len(PRACTICE_SENTENCES)
            st.session_state.assessment_result = None  # Clear previous assessment
            st.rerun()

        st.markdown("---")

        # Audio recording section
        st.subheader("Record Your Pronunciation")

        # Audio input widget (microphone recording)
        audio_value = st.audio_input("Click to record")

        if audio_value is not None:
            st.session_state.audio_data = audio_value.read()
            st.audio(st.session_state.audio_data, format='audio/wav')

            if st.button("Assess Pronunciation", type="primary", use_container_width=True):
                with st.spinner("Analyzing your pronunciation..."):
                    result = assess_pronunciation(
                        st.session_state.audio_data,
                        st.session_state.practice_sentence
                    )
                    st.session_state.assessment_result = result

    with col2:
        st.subheader("Assessment Results")

        if st.session_state.assessment_result:
            format_assessment_result(st.session_state.assessment_result)
        else:
            st.info("Record yourself reading the practice sentence to receive detailed feedback on your pronunciation!")

            # Display tips
            with st.expander("Recording Tips", True):
                st.markdown("""
                1. **Find a quiet space** - Minimize background noise
                2. **Speak clearly** - Don't rush through the sentence
                3. **Natural pace** - Speak at your normal speed
                4. **Stay close to mic** - But not too close (6-8 inches)
                5. **Read completely** - Read the entire sentence
                6. **Relax** - Take a breath before starting
                """)

            # Display common pronunciation challenges
            with st.expander("Common Pronunciation Challenges", True):
                st.markdown("""
                - **TH sounds**: Practice 'th' in words like "think", "this", "weather"
                - **V vs W**: Distinguish between 'v' and 'w' (very vs. where)
                - **Word stress**: Emphasize the right syllable in multi-syllable words
                - **Linking**: Connect words smoothly in sentences
                - **Rhythm**: Maintain natural English stress-timed rhythm
                """)


if __name__ == "__main__":
    main()
