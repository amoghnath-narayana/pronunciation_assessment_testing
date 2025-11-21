"""Prompts for Gemini analysis of Azure pronunciation results."""

import json

# Concise system prompt for Gemini analysis
AZURE_ANALYSIS_SYSTEM_PROMPT = """You analyze Azure Speech pronunciation scores for young Indian English learners (ages 5-7).
Be encouraging. Use simple words. Focus on 1-2 key issues max."""


def build_azure_analysis_prompt(azure_result: dict, reference_text: str) -> str:
    """Build prompt for Gemini with full Azure phoneme-level details."""
    import logfire

    # Extract full Azure data including phoneme details
    nbest = azure_result.get("NBest", [{}])[0]
    scores = nbest.get("PronunciationAssessment", {})
    words = nbest.get("Words", [])
    recognized_text = nbest.get("Display", "").strip()

    logfire.info(
        "Building Gemini prompt with full phoneme data",
        total_words=len(words),
        pron_score=scores.get("PronScore", 0),
    )

    # Build detailed word data with phoneme information
    detailed_words = []
    for w in words:
        wa = w.get("PronunciationAssessment", {})
        word_data = {
            "word": w.get("Word"),
            "accuracy_score": wa.get("AccuracyScore", 100),
            "error_type": wa.get("ErrorType", "None"),
        }

        # Include phoneme details if available
        phonemes = w.get("Phonemes", [])
        if phonemes:
            word_data["phonemes"] = []
            for p in phonemes:
                pa = p.get("PronunciationAssessment", {})
                phoneme_data = {
                    "phoneme": p.get("Phoneme"),
                    "accuracy_score": pa.get("AccuracyScore", 100),
                }
                # Include NBestPhonemes to show what sound was actually made
                nbest_phonemes = pa.get("NBestPhonemes", [])
                if nbest_phonemes:
                    phoneme_data["actual_sounds"] = [
                        {"phoneme": np.get("Phoneme"), "score": np.get("Score")}
                        for np in nbest_phonemes[:3]  # Top 3 candidates
                    ]
                word_data["phonemes"].append(phoneme_data)

        # Include syllable details if available
        syllables = w.get("Syllables", [])
        if syllables:
            word_data["syllables"] = [
                {
                    "syllable": s.get("Syllable"),
                    "accuracy_score": s.get("PronunciationAssessment", {}).get(
                        "AccuracyScore", 100
                    ),
                }
                for s in syllables
            ]

        detailed_words.append(word_data)

    # Log words with issues for debugging
    problematic_words = [
        w
        for w in detailed_words
        if w.get("accuracy_score", 100) < 90 or w.get("error_type") != "None"
    ]

    logfire.info(
        "Detailed word data prepared",
        word_count=len(detailed_words),
        has_phonemes=any("phonemes" in w for w in detailed_words),
        problematic_words=problematic_words,
    )

    # Log full word details for debugging substitution errors
    logfire.debug(
        "Full Azure word details",
        words=[
            {
                "word": w.get("word"),
                "score": w.get("accuracy_score"),
                "error": w.get("error_type"),
            }
            for w in detailed_words
        ],
    )

    return f"""Expected Sentence: "{reference_text}"
What Student Said: "{recognized_text}"

Overall Scores:
- Pronunciation: {scores.get("PronScore", 0)}
- Accuracy: {scores.get("AccuracyScore", 0)}
- Fluency: {scores.get("FluencyScore", 0)}
- Completeness: {scores.get("CompletenessScore", 0)}
- Prosody: {scores.get("ProsodyScore", 0)}

Word-Level Details (with phoneme analysis):
{json.dumps(detailed_words, indent=2)}

Instructions:
1. FIRST: Compare the expected sentence with what the student actually said. If they said a DIFFERENT WORD (e.g., "bat" instead of "mat"), this is a CRITICAL error - tell them they said the wrong word!
2. THEN: Analyze the phoneme-level data to identify which specific sounds were mispronounced.
3. For each problematic word, explain which letter/sound was wrong and how to fix it.
4. Use simple language for 5-7 year old Indian English learners.

Return JSON:
{{"summary_text":"<1-2 sentence encouragement>","overall_scores":{{"pronunciation":<n>,"accuracy":<n>,"fluency":<n>,"completeness":<n>,"prosody":<n>}},"word_level_feedback":[{{"word":"<word>","issue":"<which sound was wrong OR wrong word said>","suggestion":"<how to say it correctly>","severity":"critical|minor"}}],"prosody_feedback":"<rhythm tip or null>"}}

Rules:
- Word substitutions (saying wrong word) are ALWAYS "critical" severity
- Focus on words with accuracy < 90 or phonemes with accuracy < 80
- Max 3 items in word_level_feedback
- Keep explanations very simple and encouraging"""



