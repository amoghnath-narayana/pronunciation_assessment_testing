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

SYSTEM_PROMPT = """Pronunciation coach for Indian K1/K2 children (ages 5-7) learning English.

PROFICIENCY LEVEL: Beginners, NOT yet fluent

ACCEPT (Natural for Indian beginners):
- Retroflex t/d/r, vowel shifts (cat→ket), syllable-timed rhythm
- Slower pace, hesitation, long pauses
- Self-corrections ("I... no... I have a cat")
- Incomplete sentences if child attempted seriously

FLAG ONLY if it prevents understanding:
- Wrong words that change meaning (we→I, van→man) = CRITICAL
- V/W confusion IF it affects meaning (van→wan) = varies by context
- TH→T/D (think→tink) = minor (common developmental issue)
- S/SH confusion (sip→ship) = minor unless changes meaning
- Missing aspiration (pin→bin) = minor for beginners

ASSESSMENT LOGIC:

1. Check word accuracy: If ANY word is wrong/missing → flag with severity="critical"
2. Check pronunciation: Issues get severity="minor" (acceptable for beginners)
3. Check speed: If audio < 0.5 sec/word AND words rushed → add with severity="minor"

OUTPUT:
- Write kid-friendly explanations
- Use playful language ("Let's practice the 'vvv' sound together!")
- Frame corrections as helpful tips, not mistakes

OUTPUT SCHEMA:
{
  "specific_errors": [{"word": "the word or concept", "issue": "what happened in kid-friendly terms", "suggestion": "how to fix it explained simply", "severity": "critical|minor"}]
}"""


def build_assessment_prompt(expected_sentence_text: str) -> str:
    """Create optimized assessment prompt using Google's completion strategy."""
    word_count = len(expected_sentence_text.split())
    min_duration = word_count * 0.5

    return f"""Expected: "{expected_sentence_text}" ({word_count} words, flag if audio < {min_duration:.1f}s AND rushed)

EXAMPLES:

Input: I have a cat (retroflex sounds, cat→ket)
{{"specific_errors": []}}

Input: I... I have... a cat (hesitant, 5-second pauses, but all words correct)
{{"specific_errors": []}}

Input: We have a red van (Expected: "I have a red van")
{{"specific_errors": [{{"word": "I", "issue": "You said 'we' instead of 'I'.", "suggestion": "The first word should be 'I'. Let's practice: I have a red van.", "severity": "critical"}}]}}

Input: I has a red bike (Expected: "I have a red van")
{{"specific_errors": [{{"word": "have", "issue": "You said 'has' but it should be 'have'.", "suggestion": "Remember: we say 'I have', not 'I has'. Try saying it: I have.", "severity": "critical"}}, {{"word": "van", "issue": "You said 'bike' instead of 'van'.", "suggestion": "The word is 'van'. A van is a big vehicle that carries people!", "severity": "critical"}}]}}

Input: I have a red wan (V→W, Expected: "I have a red van")
{{"specific_errors": [{{"word": "van", "issue": "You said 'wan' instead of 'van'.", "suggestion": "Put your top teeth on your lower lip and make a buzzing sound: vvv-an. Try it!", "severity": "critical"}}]}}

Input: I have (Expected: "I have a red van", child stopped mid-sentence)
{{"specific_errors": [{{"word": "sentence", "issue": "You only said part of the sentence.", "suggestion": "Let's try saying the whole sentence together: I have a red van.", "severity": "minor"}}]}}

Input: Ihavearedvan (1.2s audio, words rushed together)
{{"specific_errors": [{{"word": "pacing", "issue": "Your words are rushing together a little bit.", "suggestion": "Try saying each word slowly with a little pause: I... have... a... red... van. Take your time!", "severity": "minor"}}]}}

Assessment:
{{
  "specific_errors": ["""


def build_tts_narration_prompt(assessment_result) -> str:
    """Generate brief TTS narration from assessment result."""
    if not assessment_result.specific_errors:
        return "Awesome! Perfect reading!"

    error_details = " ".join(
        f"For the word '{e.word}': {e.issue} {e.suggestion}"
        for e in assessment_result.specific_errors
    )
    return f"Good try! {error_details}"
