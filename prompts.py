"""
Centralized prompt management for pronunciation assessment.
Optimized following Google Gemini best practices for cost-efficiency.

Optimization improvements:
- Uses completion strategy (starts JSON structure)
- Minimal schema with only 2 fields for TTS-friendly output
- Concise examples without redundant text
- OUTPUT SCHEMA in system prompt for clarity
- Follows Google's few-shot learning patterns
- Leverages Gemini's native audio duration perception for speed analysis
"""

SYSTEM_PROMPT = """You are an expert pronunciation coach for Indian K1-K2 children (ages 5-7) learning English.

CORE COMPETENCIES:
- Native audio analysis with accent awareness
- Child-appropriate feedback generation
- Pattern recognition for common pronunciation errors

ACCENT ACCEPTANCE (Indian English):
- Retroflex consonants (t, d, n)
- Vowel shifts (e.g., "bed" → "bade")
- Syllable-timed rhythm (vs. stress-timed)
- Slower speaking pace with natural pauses

ERROR CLASSIFICATION:
- CRITICAL: Wrong/missing words, word substitutions
- MINOR: Pronunciation variations, hesitations, pacing issues, self-corrections

FEEDBACK STYLE:
- Encouraging and positive
- Simple vocabulary (K1-K2 level)
- Specific and actionable
- Focus on one improvement at a time"""


def build_assessment_prompt(expected_sentence_text: str) -> str:
    """Create optimized assessment prompt using Gemini 3 audio capabilities."""
    return f"""Expected: "{expected_sentence_text}"

AUDIO ANALYSIS:
- Listen for: word accuracy, pronunciation clarity, pacing
- Accept: Indian English accents (retroflex sounds, vowel shifts)
- Flag: Wrong words (critical), mispronunciation (minor), unnatural rushing (minor)

NOTE: "word" field must be the expected word from the sentence, NOT what user said.

EXAMPLES:

Audio: "I have a cat" (clear, correct)
{{"specific_errors": []}}

Audio: "I has a red bike" (wrong words)
{{"specific_errors": [{{"word": "have", "issue": "You said 'has'.", "suggestion": "Try 'have'.", "severity": "critical"}}, {{"word": "van", "issue": "You said 'bike'.", "suggestion": "Say 'van'.", "severity": "critical"}}]}}

Audio: "I have" (incomplete)
{{"specific_errors": [{{"word": "sentence", "issue": "Only said part of sentence.", "suggestion": "Say the whole sentence.", "severity": "minor"}}]}}

Audio: "I haaave a vaaaan" (stretched pronunciation)
{{"specific_errors": [{{"word": "pronunciation", "issue": "Words were stretched out.", "suggestion": "Speak naturally.", "severity": "minor"}}]}}

Assessment:
{{
  "specific_errors": ["""


def build_tts_narration_prompt(assessment_result) -> str:
    """Generate brief TTS narration from assessment result."""
    if not assessment_result.specific_errors:
        return "Awesome! Perfect reading!"

    error_details = " ".join(
        f"{e.issue} {e.suggestion}"
        for e in assessment_result.specific_errors
    )
    return f"Good try! {error_details}"
