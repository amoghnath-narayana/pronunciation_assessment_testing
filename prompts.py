"""Prompts for Gemini analysis of Azure pronunciation results."""

import json

# System prompt - concise and role-focused per Gemini best practices
AZURE_ANALYSIS_SYSTEM_PROMPT = """You are a pronunciation assessment assistant.

Your job is to:
1. Extract information from Azure Speech API JSON data
2. Identify the most critical issue (if any): wrong words first, then pronunciation errors
3. Provide one piece of encouraging feedback for children aged 5-7 learning English

Important:
- Word substitutions (wrong word spoken) are CRITICAL priority
- Accept Indian English accent variations as correct
- Only flag clear pronunciation errors (AccuracyScore < 50)
- Use simple, child-friendly language"""


def build_azure_analysis_prompt(azure_result: dict, reference_text: str) -> str:
    """
    Build prompt for Gemini with full Azure response data.

    Follows Gemini prompting best practices:
    - Provides complete context (full Azure JSON response)
    - Clear structure with XML delimiters
    - Few-shot examples demonstrating expected behavior
    - Direct, concise instructions
    - Output prefix strategy for JSON generation

    This approach lets Gemini handle all the analysis logic including:
    - Word substitution detection
    - Phoneme analysis
    - Accent variation handling
    - Feedback generation
    """
    import logfire

    # Extract basic info for logging and context
    nbest = azure_result.get("NBest", [{}])[0]
    recognized_text = nbest.get("Display", "").strip()
    scores = nbest.get("PronunciationAssessment", {})

    logfire.info(
        "Building Gemini prompt with full Azure response",
        reference_text=reference_text,
        recognized_text=recognized_text,
        pron_score=scores.get("PronScore", 0),
        azure_response_size_bytes=len(json.dumps(azure_result)),
    )

    return f"""Analyze this pronunciation assessment for a child (age 5-7) learning English.

EXPECTED TEXT: "{reference_text}"
RECOGNIZED TEXT: "{recognized_text}"

AZURE SPEECH ASSESSMENT DATA:
{json.dumps(azure_result, indent=2)}

YOUR TASK:
Extract the assessment information from the Azure data above and provide feedback.

STEP 1 - Extract Overall Scores:
- Get scores from NBest[0].PronunciationAssessment
- Set overall_scores.pronunciation = PronScore
- Set overall_scores.accuracy = AccuracyScore
- Set overall_scores.fluency = FluencyScore
- Set overall_scores.completeness = CompletenessScore

STEP 2 - Check for Word Substitutions (HIGHEST PRIORITY):
- Split expected text "{reference_text}" into words
- Compare with NBest[0].Words[].Word to find mismatches
- Example: If expected "cat" but Azure shows Word="bat", this is a substitution
- Check ErrorType field for "Substitution" or "Omission"
- If ANY substitution found: Add ONE feedback item with severity="critical"
  - word = what they said (wrong word)
  - letter = the wrong word
  - expected_sound = correct word
  - actual_sound = what they said
  - suggestion = "You said '[wrong]' but the word is '[correct]'"

STEP 3 - Check Pronunciation (ONLY if no substitutions):
- Look through Words[].Phonemes[] for any with AccuracyScore < 50
- Use NBestPhonemes[0].Phoneme to see what sound they actually made
- SKIP these (Indian English variations, acceptable):
  - θ or ð pronounced as 't' or 'd' (th sounds)
  - Retroflex sounds
  - 'v'/'w' confusion
  - 'r' coloring
- If problematic phoneme found: Add ONE feedback item with severity="minor"
  - word = the word containing the issue
  - letter = the letter(s) for that phoneme
  - expected_sound = convert IPA to simple (ð→"th", æ→"a", ɪ→"i", etc)
  - actual_sound = convert actual phoneme to simple
  - suggestion = child-friendly tip

STEP 4 - Create Summary:
- If perfect (no issues): "Wonderful! You said it perfectly!"
- If good (scores >80): "Great job! Your pronunciation is excellent."
- If substitution: "Good try! Let's practice the right word."
- If pronunciation issue: "Great job! Let's work on one sound."

RULES:
- Maximum 1 feedback item (or empty list if perfect)
- Substitutions always take priority over pronunciation
- Use encouraging, child-friendly language
- Convert IPA phonemes to simple descriptions: ð/θ→th, æ→a, ɪ→i, ɛ→e, ə→uh, ɔ→o, etc."""



