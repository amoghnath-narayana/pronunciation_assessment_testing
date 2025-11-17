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

SYSTEM_PROMPT = """Pronunciation coach for Indian K1-K2 children learning English.

ACCEPT: Retroflex sounds, vowel shifts, syllable-timed rhythm, slower pace, hesitation, pauses, self-corrections, incomplete attempts.

FLAG: Wrong/missing words = "critical". Pronunciation issues = "minor". Rushed speech = "minor".

Use encouraging, kid-friendly language."""


def build_assessment_prompt(expected_sentence_text: str) -> str:
    """Create optimized assessment prompt using Google's completion strategy."""
    word_count = len(expected_sentence_text.split())
    min_duration = word_count * 0.5

    return f"""Expected: "{expected_sentence_text}" ({word_count} words, flag if audio < {min_duration:.1f}s AND rushed, word = expected word only)

EXAMPLES:

Input: I have a cat
{{"specific_errors": []}}

Input: I has a red bike
{{"specific_errors": [{{"word": "have", "issue": "You said 'has' instead of 'have'.", "suggestion": "Say 'I have', not 'I has'.", "severity": "critical"}}, {{"word": "van", "issue": "You said 'bike' instead of 'van'.", "suggestion": "The word is 'van'.", "severity": "critical"}}]}}

Input: I have
{{"specific_errors": [{{"word": "sentence", "issue": "You only said part of the sentence.", "suggestion": "Try saying the whole sentence.", "severity": "minor"}}]}}

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
