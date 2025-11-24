"""Prompts for Gemini analysis of Azure pronunciation results."""

import json
import logfire

from models.assessment_models import AzureRecognitionResult

# System prompt - concise and role-focused per Gemini best practices
AZURE_ANALYSIS_SYSTEM_PROMPT = """You are a pronunciation assistant for children aged 5-7 learning English.

Identify pronunciation mistakes by comparing expected vs actual phonemes.

Rules:
- Focus on PHONEME MISMATCHES (expected phoneme ≠ actual phoneme produced)
- Ignore numerical accuracy scores - only check if phonemes match
- List wrong words first (severity "critical"), then phoneme mistakes (severity "minor")
- Check EVERY phoneme in EVERY word
- Skip Indian English variations (th→t/d, v↔w, r-coloring)
- Use simple, child-friendly language"""


def build_azure_analysis_prompt(
    azure_response: AzureRecognitionResult, reference_text: str
) -> str:
    """
    Build prompt for Gemini with full Azure response data.

    Accepts Pydantic model for type safety, converts to dict for JSON serialization.

    Args:
        azure_response: Validated Azure recognition result
        reference_text: Expected text for comparison

    Returns:
        Structured prompt with Azure data and analysis instructions
    """
    # Convert Pydantic model to dict for JSON serialization
    azure_dict = azure_response.model_dump()

    # Extract info for logging (using Pydantic properties for type safety)
    recognized_text = azure_dict.get("NBest", [{}])[0].get("Display", "").strip()
    scores = azure_response.pronunciation_scores

    # Build the prompt - focus on phoneme mismatches and word substitutions only
    prompt = f"""Analyze pronunciation for a child (age 5-7).

Expected: "{reference_text}"
Recognized: "{recognized_text}"

Azure Data:
{json.dumps(azure_dict, indent=2)}

Instructions:

1. EXTRACT SCORES from NBest[0].PronunciationAssessment (just copy them):
   - pronunciation = PronScore
   - accuracy = AccuracyScore  
   - fluency = FluencyScore
   - completeness = CompletenessScore

2. FIND PRONUNCIATION MISTAKES:
   
   A. Wrong words (word substitutions/omissions):
      - Compare expected "{reference_text}" with Words[].Word
      - If ErrorType is "Omission":
        * severity = "critical"
        * word = the missing word
        * expected_sound = correct word
        * actual_sound = "skipped"
        * suggestion = "You skipped the word '[word]'. Try saying it!"
      - If ErrorType is "Insertion":
        * severity = "critical"  
        * word = the extra word
        * expected_sound = "none"
        * actual_sound = what they said
        * suggestion = "You added an extra word '[word]' that wasn't in the sentence"
   
   B. Letter/sound pronunciation mistakes (check EVERY word's Phonemes array):
      - For EACH phoneme in Words[].Phonemes[]:
        1. Get expected_phoneme = Phoneme (the phoneme they should say)
        2. Get actual_phoneme = NBestPhonemes[0].Phoneme (the phoneme they actually said)
        3. If expected_phoneme ≠ actual_phoneme (they don't match exactly):
           * Skip these common variations (NOT mistakes):
             - Indian English: th→t/d, v↔w, r-coloring
             - Schwa variations: ə↔ʌ, ə↔ɪ (very similar sounds)
             - Minor vowel shifts: oʊ↔ɔ, ɔ↔ɑ
           * Only report if AccuracyScore < 50 (significant mispronunciation)
           * severity = "minor" (always minor for phoneme issues)
           * word = the word containing this phoneme
           * letter = letter(s) making that sound (from Syllables[].Grapheme if available, otherwise guess from word)
           * expected_sound = expected_phoneme in simple terms (æ→"a as in cat", ɛ→"e as in red", ɪ→"i as in sit", i→"ee as in see")
           * actual_sound = actual_phoneme in simple terms
           * suggestion = "The '[letter]' in '[word]' should sound like '[expected]', but you said '[actual]'"
      
      IMPORTANT: 
      - Only flag if expected_phoneme ≠ actual_phoneme AND AccuracyScore < 50
      - Ignore minor variations and scores above 50 (they got it close enough)
      - CHECK EVERY PHONEME IN EVERY WORD!
      
      EXAMPLES:
      - Phoneme="ɛ", NBestPhonemes[0]="æ", AccuracyScore=47 → REPORT (different sound, low score)
      - Phoneme="ɹ", NBestPhonemes[0]="ɹ", AccuracyScore=63 → NO mistake (same phoneme)
      - Phoneme="ð", NBestPhonemes[0]="n", AccuracyScore=71 → NO mistake (score > 50, close enough)
      - Phoneme="ə", NBestPhonemes[0]="oʊ", AccuracyScore=59 → NO mistake (score > 50, close enough)
      - Phoneme="æ", NBestPhonemes[0]="b", AccuracyScore=37 → REPORT (different sound, low score)

3. SUMMARY:
   - No mistakes: "Wonderful! You said it perfectly!"
   - 1-2 phoneme mistakes: "Great job! Let's work on [number] sound(s)."
   - 3+ mistakes or wrong words: "Good try! Let's practice together."

Return ALL mistakes in word_level_feedback array."""

    # Log prompt info
    logfire.info(
        "Building Gemini prompt",
        reference_text=reference_text,
        recognized_text=recognized_text,
        pron_score=scores.PronScore if scores else 0,
        azure_response_size_bytes=len(json.dumps(azure_dict)),
        prompt_length=len(prompt),
    )

    # Log the full prompt for debugging (use print to avoid logfire format issues with JSON)
    print("\n" + "=" * 80)
    print("FULL GEMINI PROMPT:")
    print("=" * 80)
    if len(prompt) > 3000:
        print(
            prompt[:3000]
            + "\n...[TRUNCATED - Full length: "
            + str(len(prompt))
            + " chars]..."
        )
    else:
        print(prompt)
    print("=" * 80 + "\n")

    return prompt
