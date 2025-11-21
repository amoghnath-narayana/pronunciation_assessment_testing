"""Prompts for Gemini analysis of Azure pronunciation results."""

import json

# Concise system prompt for Gemini analysis
AZURE_ANALYSIS_SYSTEM_PROMPT = """Analyze pronunciation for Indian English learners (ages 5-7). 

CONTEXT: Indian English has natural variations (retroflex sounds, different 'r', 'v'/'w' patterns). Accept these as valid unless severely unclear.

GUIDELINES:
- Be very encouraging and supportive
- Only flag issues if phoneme accuracy <70 (not <80) - be lenient
- Accept Indian English accent patterns as correct
- Focus on clarity, not native-like perfection
- Use simple, child-friendly language
- Celebrate effort and progress

CRITICAL: In the "issue" field, always specify the exact letter(s) from the word that need work (e.g., "The 'th' sound is unclear", "The 'r' sound is unclear"). This is essential for highlighting."""


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

ANALYSIS RULES FOR INDIAN ENGLISH LEARNERS:
1. Be LENIENT - Only flag issues if phoneme accuracy <70 (not <80)
2. Accept Indian English accent variations (retroflex sounds, different 'r', 'v'/'w' patterns)
3. Ignore minor accent differences - focus on CLARITY only
4. If overall score >75, give mostly positive feedback with at most 1 gentle suggestion
5. For scores 60-75, provide 1-2 specific tips
6. For scores <60, provide 2-3 clear, actionable tips

FEEDBACK FORMAT:
- Identify the EXACT LETTER(S) in the word that correspond to the problematic phoneme
- In the "issue" field, write EXACTLY: "The '<letter>' sound is unclear" (e.g., "The 'th' sound is unclear", "The 'r' sound is unclear")
- The letter(s) MUST match the actual letters in the word for highlighting to work
- Use child-friendly language: "Try saying the 'th' like putting your tongue between your teeth"

Max 3 feedback items. Prioritize encouragement over criticism.

Return JSON:
{{"summary_text":"<warm encouragement>","overall_scores":{{"pronunciation":<n>,"accuracy":<n>,"fluency":<n>,"completeness":<n>,"prosody":<n>}},"word_level_feedback":[{{"word":"<word>","issue":"The '<exact_letter(s)>' sound is unclear","suggestion":"<simple, friendly tip>","severity":"critical|minor"}}],"prosody_feedback":"<tip or null>"}}"""



