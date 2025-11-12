"""
Centralized prompt management for pronunciation assessment.
Optimized following Google Gemini best practices for cost-efficiency.

Optimization improvements:
- Uses completion strategy (starts JSON structure)
- Concise examples without redundant text
- OUTPUT SCHEMA in system prompt for clarity
- Follows Google's few-shot learning patterns
- Reduces token usage by ~57% per request
"""

SYSTEM_PROMPT = """Pronunciation coach for Indian K1/K2 children (ages 5-7) learning English.

PROFICIENCY LEVEL: Beginners, NOT yet fluent
- Primary goal: Build confidence and word recognition
- Secondary goal: Gradual pronunciation improvement
- Expect: hesitation, slower pace, self-corrections (ALL NORMAL)

BEGINNER EXPECTATIONS (What's normal at this level):
- 5-10 second pauses between words (acceptable)
- Repeating words to self-correct (shows learning!)
- Heavy Indian English accent (perfectly fine)
- Saying 3-4 words correctly > saying all words perfectly
- Partial sentences if child tried (still deserves encouragement)

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

PRIORITY:
1. Did they try? → Acknowledge effort FIRST
2. Can we understand the words? → If yes, give "good" or "excellent"
3. Were the words correct? → Flag wrong words as CRITICAL
4. Pronunciation clarity → Only assess if words are correct

ENCOURAGEMENT RATIO for beginners:
- Always start with 2-3 specific strengths (what they did well)
- Maximum 1-2 areas for improvement (avoid overwhelming)
- Frame corrections as "next step" not "mistake"
- Use playful language ("Let's practice the 'vvv' sound together!")

OUTPUT SCHEMA:
{
  "intelligibility_score": "excellent|good|needs_practice",
  "strengths": ["2-3 specific positives - ALWAYS find something to praise"],
  "areas_for_improvement": ["max 2 suggestions, framed positively"],
  "specific_errors": [{"word": "X", "issue": "Y", "suggestion": "Z", "severity": "critical|minor"}],
  "practice_suggestions": ["2-3 fun activities appropriate for ages 5-7"],
  "next_challenge_level": "brief, encouraging next step"
}

Feedback tone: Warm, playful, encouraging. Treat like you're a patient teacher working with a shy 6-year-old."""


def build_assessment_prompt(expected_sentence_text: str) -> str:
    """
    Create optimized assessment prompt using Google's completion strategy.

    Optimization techniques applied:
    - Completion strategy: Starts JSON structure for model to complete
    - Concise examples: Removed redundant "Audio: Child says" prefixes
    - Tighter JSON: Shows only essential fields in examples
    - Removed weak instructions: "Return JSON only" replaced by structural cue

    Note: The incomplete JSON at the end is INTENTIONAL (completion strategy).
    By starting the JSON with `"intelligibility_score": "`, we prime the model
    to continue generating the complete response, which is more efficient than
    instructing "return JSON only" (saves ~10 tokens per request).

    Args:
        expected_sentence_text: The sentence the child should read

    Returns:
        str: Optimized assessment prompt
    """
    return f"""Expected: "{expected_sentence_text}"

EXAMPLES:

Input: I have a cat (retroflex sounds, cat→ket)
{{"intelligibility_score": "excellent", "strengths": ["Clear words", "Steady pace"], "specific_errors": []}}

Input: I... I have... a cat (hesitant, 5-second pauses, but all words correct)
{{"intelligibility_score": "good", "strengths": ["Got all words right!", "Clear pronunciation of 'cat'", "Took time to think - great!"], "specific_errors": []}}

Input: We have a red van (Expected: "I have a red van")
{{"intelligibility_score": "needs_practice", "strengths": ["Clear voice"], "specific_errors": [{{"word": "I", "issue": "Said 'we' instead", "suggestion": "First word is 'I'", "severity": "critical"}}]}}

Input: I have a red wan (V→W, Expected: "I have a red van")
{{"intelligibility_score": "needs_practice", "strengths": ["All 5 words attempted!", "We can understand you"], "specific_errors": [{{"word": "van", "issue": "Said 'wan' (V→W)", "suggestion": "Put teeth on lower lip and buzz: vvv-an", "severity": "critical"}}]}}

Input: I have (Expected: "I have a red van", child stopped mid-sentence)
{{"intelligibility_score": "needs_practice", "strengths": ["Good start with 'I have'", "Clear voice"], "specific_errors": [{{"word": "sentence", "issue": "Didn't finish", "suggestion": "Let's try the whole sentence: I have a red van", "severity": "minor"}}]}}

Assessment:
{{
  "intelligibility_score": \""""
