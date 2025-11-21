"""Prompts for Gemini analysis of Azure pronunciation results."""

import json

# Concise system prompt for Gemini analysis
AZURE_ANALYSIS_SYSTEM_PROMPT = """Analyze pronunciation for Indian English learners (ages 5-7). Be encouraging, use simple words, focus on 1-2 key issues."""


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

    return f"""Expected: "{reference_text}"
Said: "{recognized_text}"

Scores: Pron={scores.get("PronScore", 0)} Acc={scores.get("AccuracyScore", 0)} Flu={scores.get("FluencyScore", 0)} Comp={scores.get("CompletenessScore", 0)} Pros={scores.get("ProsodyScore", 0)}

Words (phoneme data):
{json.dumps(detailed_words, indent=2)}

Analyze phonemes. Identify unclear sounds (accuracy<90 or phoneme<80). Max 3 feedback items.
Note: Azure detects unclear sounds, not word substitutions.

Return JSON:
{{"summary_text":"<encouragement>","overall_scores":{{"pronunciation":<n>,"accuracy":<n>,"fluency":<n>,"completeness":<n>,"prosody":<n>}},"word_level_feedback":[{{"word":"<word>","issue":"'<letter>' sound unclear","suggestion":"<simple tip>","severity":"critical|minor"}}],"prosody_feedback":"<tip or null>"}}"""



