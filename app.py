"""
Pronunciation Assessment Application
Using Gemini 2.5 Pro for K-12 Indian Students
"""

import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
import json

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# System prompt for pronunciation assessment
SYSTEM_PROMPT = """
English Pronunciation Assessment for K-12 Indian Students

## Role & Context
You are an AI English pronunciation tutor specifically designed for K-12 Indian students from Narayana Group schools. Your primary function is to assess and improve English pronunciation through reading exercises.

## Core Responsibilities

### 1. Content Suggestion
**Suggest age-appropriate English content for reading practice:**
- **Grades K-2:** Simple 3-7 word sentences, basic sight words, phonetic words
- **Grades 3-5:** 8-15 word sentences, common vocabulary, simple stories
- **Grades 6-8:** Complex sentences, academic vocabulary, short paragraphs
- **Grades 9-12:** Advanced sentences, technical terms, literary excerpts

**Content Guidelines:**
- Focus on commonly mispronounced sounds by Indian English speakers
- Include words with: TH sounds, V/W distinction, R sounds, schwa sounds
- Culturally appropriate and educationally relevant content
- Progressive difficulty based on grade level

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
- TH → T/D substitution (think → tink, this → dis)
- V/W confusion (very → wery, west → vest)
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

### 7. Sample Interaction Flow

1. **Greeting & Level Assessment:** "Hi! I'm here to help improve your English pronunciation. What grade are you in?"

2. **Content Suggestion:** "Let's practice with this sentence: [age-appropriate content]"

3. **Post-Recording Analysis:**
   - Listen to student's recording
   - Analyze against parameters
   - Provide structured feedback

4. **Follow-up Practice:** Suggest targeted exercises based on identified areas

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

# Sample sentences by grade level
PRACTICE_SENTENCES = {
    "K-2": [
        "The cat is very happy.",
        "I want three red apples.",
        "This is my new book.",
        "We go to school together.",
        "Thank you for the help."
    ],
    "3-5": [
        "The weather is beautiful today with clear blue skies.",
        "My favorite subject is mathematics because it's very interesting.",
        "We should always think before we speak.",
        "The village festival brings everyone together.",
        "I practice writing every evening after dinner."
    ],
    "6-8": [
        "The scientific method involves observation, hypothesis, experimentation, and conclusion.",
        "Cultural diversity enriches our understanding of the world around us.",
        "Technology has revolutionized the way we communicate with each other.",
        "Environmental conservation is everyone's responsibility in the modern world.",
        "Critical thinking skills are essential for academic success."
    ],
    "9-12": [
        "The intersection of artificial intelligence and ethics presents unprecedented challenges for modern society.",
        "Analyzing literary themes requires careful attention to authorial intent and contextual nuances.",
        "Sustainable development goals necessitate collaborative efforts across governmental and private sectors.",
        "The synthesis of theoretical knowledge and practical application defines true expertise.",
        "Contemporary global economics demonstrates the interconnectedness of international markets."
    ]
}


def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if 'audio_data' not in st.session_state:
        st.session_state.audio_data = None
    if 'assessment_result' not in st.session_state:
        st.session_state.assessment_result = None
    if 'selected_grade' not in st.session_state:
        st.session_state.selected_grade = "3-5"
    if 'practice_sentence' not in st.session_state:
        st.session_state.practice_sentence = ""
    if 'recording_status' not in st.session_state:
        st.session_state.recording_status = "ready"


def get_practice_sentence(grade_level: str, index: int = 0) -> str:
    """Get a practice sentence for the selected grade level"""
    sentences = PRACTICE_SENTENCES.get(grade_level, PRACTICE_SENTENCES["3-5"])
    return sentences[index % len(sentences)]


def assess_pronunciation(audio_data: bytes, expected_text: str, grade_level: str) -> Dict:
    """
    Send audio to Gemini API for pronunciation assessment
    """
    try:
        # Initialize the Gemini model (using latest version)
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
            system_instruction=SYSTEM_PROMPT
        )

        # Create a temporary file for the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_file.write(audio_data)
            tmp_file_path = tmp_file.name

        # Upload the audio file to Gemini
        audio_file = genai.upload_file(tmp_file_path)

        # Create the prompt
        prompt = f"""
        Grade Level: {grade_level}
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

        # Generate response
        response = model.generate_content([prompt, audio_file])

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

    # Display overall scores with color coding
    st.subheader("Overall Assessment")

    cols = st.columns(3)
    score_emojis = {"Yes": "[PASS]", "No": "[FAIL]", "NA": "[N/A]"}
    score_colors = {"Yes": "green", "No": "red", "NA": "gray"}

    with cols[0]:
        score = result["overall_scores"]["phonetic_accuracy"]
        st.metric(
            "Phonetic Accuracy",
            f"{score_emojis[score]} {score}",
        )
        if result["detailed_feedback"]["phonetic_accuracy_details"]:
            st.caption(result["detailed_feedback"]["phonetic_accuracy_details"])

    with cols[1]:
        score = result["overall_scores"]["fluency"]
        st.metric(
            "Fluency",
            f"{score_emojis[score]} {score}",
        )
        if result["detailed_feedback"]["fluency_details"]:
            st.caption(result["detailed_feedback"]["fluency_details"])

    with cols[2]:
        score = result["overall_scores"]["prosody"]
        st.metric(
            "Prosody",
            f"{score_emojis[score]} {score}",
        )
        if result["detailed_feedback"]["prosody_details"]:
            st.caption(result["detailed_feedback"]["prosody_details"])

    # Display strengths
    if result.get("strengths"):
        st.subheader("Strengths")
        for strength in result["strengths"]:
            st.success(f"- {strength}")

    # Display areas for improvement
    if result.get("areas_for_improvement"):
        st.subheader("Areas for Improvement")
        for area in result["areas_for_improvement"]:
            st.info(f"- {area}")

    # Display specific errors
    if result.get("specific_errors") and len(result["specific_errors"]) > 0:
        st.subheader("Specific Corrections")
        for error in result["specific_errors"]:
            with st.expander(f"Word: {error.get('word', 'N/A')}"):
                st.write(f"**Issue:** {error.get('issue', 'N/A')}")
                st.write(f"**Suggestion:** {error.get('suggestion', 'N/A')}")

    # Display practice suggestions
    if result.get("practice_suggestions"):
        st.subheader("Practice Suggestions")
        for i, suggestion in enumerate(result["practice_suggestions"], 1):
            st.write(f"{i}. {suggestion}")

    # Display encouragement
    if result.get("encouragement"):
        st.subheader("Keep Going!")
        st.markdown(f"*{result['encouragement']}*")

    # Display next challenge
    if result.get("next_challenge"):
        st.subheader("Next Challenge")
        st.info(result["next_challenge"])


def main():
    """Main application function"""
    st.set_page_config(
        page_title="Pronunciation Assessment",
        page_icon="",
        layout="wide"
    )

    # Initialize session state
    initialize_session_state()

    # App header
    st.title("English Pronunciation Assessment")
    st.markdown("*Designed for K-12 Indian Students*")
    st.markdown("---")

    # Sidebar for settings
    with st.sidebar:
        st.header("Settings")

        # Grade selection
        st.session_state.selected_grade = st.selectbox(
            "Select Grade Level",
            options=["K-2", "3-5", "6-8", "9-12"],
            index=1
        )

        # Sentence selection
        st.subheader("Practice Sentences")
        sentence_index = st.number_input(
            "Sentence Number",
            min_value=1,
            max_value=5,
            value=1
        ) - 1

        # About section
        st.markdown("---")
        st.subheader("About")
        st.markdown("""
        This app helps Indian K-12 students improve their English pronunciation through:
        - Grade-appropriate practice sentences
        - AI-powered pronunciation assessment
        - Detailed feedback on phonetics, fluency, and prosody
        - Personalized improvement suggestions
        """)

    # Main content area
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Practice Sentence")

        # Get and display practice sentence
        st.session_state.practice_sentence = get_practice_sentence(
            st.session_state.selected_grade,
            sentence_index
        )

        # Display the sentence in a nice box
        st.markdown(
            f"""
            <div style="
                background-color: #f0f2f6;
                border-radius: 10px;
                padding: 20px;
                margin: 10px 0;
                border: 2px solid #4CAF50;
            ">
                <h3 style="text-align: center; color: #333;">
                    {st.session_state.practice_sentence}
                </h3>
            </div>
            """,
            unsafe_allow_html=True
        )

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
                        st.session_state.practice_sentence,
                        st.session_state.selected_grade
                    )
                    st.session_state.assessment_result = result

        # Alternative: File uploader
        st.markdown("---")
        st.markdown("**Alternative: Upload an audio file**")
        uploaded_file = st.file_uploader(
            "Choose audio file",
            type=['wav', 'mp3', 'ogg', 'm4a'],
            help="Upload a recording of you reading the sentence above"
        )

        if uploaded_file is not None:
            upload_data = uploaded_file.read()
            st.audio(upload_data, format='audio/wav')

            if st.button("Assess Uploaded Audio", type="secondary", use_container_width=True):
                with st.spinner("Analyzing your pronunciation..."):
                    result = assess_pronunciation(
                        upload_data,
                        st.session_state.practice_sentence,
                        st.session_state.selected_grade
                    )
                    st.session_state.assessment_result = result

    with col2:
        st.subheader("Assessment Results")

        if st.session_state.assessment_result:
            format_assessment_result(st.session_state.assessment_result)
        else:
            st.info("Record yourself reading the practice sentence to receive detailed feedback on your pronunciation!")

            # Display tips
            with st.expander("Recording Tips"):
                st.markdown("""
                1. **Find a quiet space** - Minimize background noise
                2. **Speak clearly** - Don't rush through the sentence
                3. **Natural pace** - Speak at your normal speed
                4. **Stay close to mic** - But not too close (6-8 inches)
                5. **Read completely** - Read the entire sentence
                6. **Relax** - Take a breath before starting
                """)

            # Display common challenges based on grade
            with st.expander("Common Challenges for Your Grade"):
                challenges = {
                    "K-2": [
                        "Focus on clear 'th' sounds (this, that, three)",
                        "Distinguish between 'v' and 'w' sounds",
                        "Practice ending consonants clearly"
                    ],
                    "3-5": [
                        "Work on word stress patterns",
                        "Practice linking words smoothly",
                        "Focus on vowel sounds in unstressed syllables"
                    ],
                    "6-8": [
                        "Master complex consonant clusters",
                        "Practice sentence stress and rhythm",
                        "Work on appropriate intonation patterns"
                    ],
                    "9-12": [
                        "Refine prosodic features for academic speaking",
                        "Practice technical vocabulary pronunciation",
                        "Focus on natural speech rhythm and flow"
                    ]
                }

                for challenge in challenges.get(st.session_state.selected_grade, []):
                    st.write(f"- {challenge}")

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #666;">
            Made for Narayana Group Students | Powered by Gemini AI
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
