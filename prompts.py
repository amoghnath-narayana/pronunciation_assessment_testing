"""Prompts for Gemini analysis of Azure pronunciation results."""

import json

# Concise system prompt for Gemini analysis
AZURE_ANALYSIS_SYSTEM_PROMPT = """You analyze Azure Speech pronunciation scores for young Indian English learners (ages 5-7).
Be encouraging. Use simple words. Focus on 1-2 key issues max."""


def build_azure_analysis_prompt(azure_result: dict, reference_text: str) -> str:
    """Build concise prompt for Gemini to analyze Azure results."""
    # Extract only essential data to reduce token usage
    nbest = azure_result.get("NBest", [{}])[0]
    scores = nbest.get("PronunciationAssessment", {})
    words = nbest.get("Words", [])

    # Build minimal word data (only problematic words)
    problem_words = []
    for w in words:
        wa = w.get("PronunciationAssessment", {})
        if wa.get("AccuracyScore", 100) < 80 or wa.get("ErrorType", "None") != "None":
            problem_words.append(
                {
                    "word": w.get("Word"),
                    "score": wa.get("AccuracyScore"),
                    "error": wa.get("ErrorType"),
                }
            )

    return f"""Reference: "{reference_text}"
Scores: Pron={scores.get("PronScore", 0)}, Acc={scores.get("AccuracyScore", 0)}, Flu={scores.get("FluencyScore", 0)}, Comp={scores.get("CompletenessScore", 0)}, Pros={scores.get("ProsodyScore", 0)}
Issues: {json.dumps(problem_words) if problem_words else "None"}

Return JSON:
{{"summary_text":"<1-2 sentence encouragement>","overall_scores":{{"pronunciation":<n>,"accuracy":<n>,"fluency":<n>,"completeness":<n>,"prosody":<n>}},"word_level_feedback":[{{"word":"<word>","issue":"<simple issue>","suggestion":"<simple fix>","severity":"critical|minor"}}],"prosody_feedback":"<rhythm tip or null>"}}

Rules: Max 2 items in word_level_feedback. Keep all text very short."""


def build_tts_narration_prompt(assessment_result) -> str:
    """Generate brief TTS narration text."""
    if not assessment_result.specific_errors:
        return "Awesome! Perfect reading!"

    # Keep it very short for TTS
    first_error = assessment_result.specific_errors[0]
    return f"Good try! {first_error.suggestion}"
