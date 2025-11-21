"""Prompts for Gemini analysis of Azure pronunciation results."""

import json

# System prompt for Gemini 3 - structured and concise
AZURE_ANALYSIS_SYSTEM_PROMPT = """You are a pronunciation assessment assistant for Indian English learners (ages 5-7).

<constraints>
- Be encouraging and supportive
- Accept Indian English accent variations (retroflex sounds, 'r', 'v'/'w', 'th'/'d')
- Only flag phoneme issues if AccuracyScore <50
- Prioritize wrong words over accent variations
- Max 3 feedback items
- Use simple, child-friendly language
</constraints>

<examples>
Input: Expected="the cat" Said="the cat" Scores: Pron=92 Acc=95 Flu=90 Comp=100
Output: {"summary_text":"Wonderful! You said it perfectly!","overall_scores":{"pronunciation":92,"accuracy":95,"fluency":90,"completeness":100},"word_level_feedback":[]}

Input: Expected="the big dog" Said="da big cat" Scores: Pron=45 Acc=40 Flu=80 Comp=100
Words: [{"word":"da","expected_word":"the","error_type":"Mispronunciation","accuracy_score":35},{"word":"big","expected_word":"big","error_type":"None","accuracy_score":95},{"word":"cat","expected_word":"dog","error_type":"Substitution","accuracy_score":30}]
Output: {"summary_text":"Good try! Let's practice a few words.","overall_scores":{"pronunciation":45,"accuracy":40,"fluency":80,"completeness":100},"word_level_feedback":[{"word":"cat","letter":"cat","expected_sound":"dog","actual_sound":"cat","suggestion":"The word is 'dog', not 'cat'","severity":"critical"},{"word":"da","letter":"th","expected_sound":"th","actual_sound":"d","suggestion":"Try putting your tongue between your teeth for 'th'","severity":"minor"}]}
</examples>"""


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
        reference_text=reference_text,
        recognized_text=recognized_text,
    )

    # Build detailed word data with phoneme information
    # Also compare recognized words with reference words to detect substitutions
    reference_words = [w.strip().lower() for w in reference_text.split()]
    
    # Build a mapping of recognized words to their positions
    detailed_words = []
    for idx, w in enumerate(words):
        wa = w.get("PronunciationAssessment", {})
        word_text = w.get("Word", "").strip().lower()
        error_type = wa.get("ErrorType", "None")
        
        # Get expected word at this position
        expected_word = reference_words[idx] if idx < len(reference_words) else None
        
        # Detect substitution: word doesn't match expected AND it's not already marked as error
        is_substitution = False
        if expected_word and word_text != expected_word:
            # This is a substitution - they said a different word
            is_substitution = True
            error_type = "Substitution"
            logfire.info(
                f"Substitution detected at position {idx}",
                expected=expected_word,
                actual=word_text,
                original_error_type=wa.get("ErrorType", "None")
            )
        
        word_data = {
            "word": w.get("Word"),
            "expected_word": expected_word,
            "accuracy_score": wa.get("AccuracyScore", 100),
            "error_type": error_type,
            "is_substitution": is_substitution,
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
    
    substitutions = [
        w for w in detailed_words if w.get("is_substitution", False)
    ]

    logfire.info(
        "Detailed word data prepared",
        word_count=len(detailed_words),
        has_phonemes=any("phonemes" in w for w in detailed_words),
        problematic_words=problematic_words,
        substitutions=substitutions,
        reference_words=reference_words,
        recognized_words=[w.get("word") for w in detailed_words],
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

    return f"""<task>
Analyze pronunciation and provide feedback for a child learning English.
</task>

<input>
Expected: "{reference_text}"
Said: "{recognized_text}"
Scores: Pron={scores.get("PronScore", 0)} Acc={scores.get("AccuracyScore", 0)} Flu={scores.get("FluencyScore", 0)} Comp={scores.get("CompletenessScore", 0)}
</input>

<data>
{json.dumps(detailed_words, indent=2)}
</data>

<instructions>
1. PRIORITY: Check is_substitution=true OR ErrorType="Substitution"/"Omission"/"Insertion"
   - If found: ALWAYS flag as critical
   - word: word they said, letter: whole word, expected_sound: expected_word, actual_sound: word, suggestion: "The word is '<expected_word>', not '<word>'", severity: "critical"

2. Check phoneme AccuracyScore <50 (be lenient)
   - For each word, check phonemes array
   - If phoneme has actual_sounds array, use actual_sounds[0].phoneme (this is what they ACTUALLY said)
   - Convert IPA to simple: b→"b", m→"m", θ→"th", d→"d", ə→"uh", k→"k", g→"g"
   - actual_sound MUST be from actual_sounds[0].phoneme, NOT "unclear"
   - word: word, letter: letter(s), expected_sound: correct sound, actual_sound: actual_sounds[0].phoneme converted to simple letter, suggestion: "Instead of '<actual>', try '<expected>' by <tip>", severity: "critical" if <40 else "minor"

3. Max 1 item only (for speed). Prioritize wrong words > severe pronunciation issues.
</instructions>

Example: If phoneme "m" has accuracy_score=45 and actual_sounds=[{{"phoneme":"b","score":100}}], then:
- expected_sound: "m"
- actual_sound: "b" (from actual_sounds[0].phoneme)
- suggestion: "Instead of 'b', try 'm' by pressing your lips together"

Return JSON:
{{"summary_text":"<encouragement>","overall_scores":{{"pronunciation":<n>,"accuracy":<n>,"fluency":<n>,"completeness":<n>}},"word_level_feedback":[{{"word":"<word>","letter":"<letter>","expected_sound":"<expected>","actual_sound":"<actual>","suggestion":"<tip>","severity":"critical|minor"}}]}}"""



