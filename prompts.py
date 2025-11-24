"""Prompts for Gemini analysis of Azure pronunciation results."""

import json
import logfire

from models.assessment_models import AzureRecognitionResult

# System prompt - concise and role-focused per Gemini best practices
AZURE_ANALYSIS_SYSTEM_PROMPT = """You are a pronunciation assessment assistant for children aged 5-7 learning English.

Extract Azure Speech API data and provide encouraging feedback.

Rules:
- List ALL problem words (wrong words first, then pronunciation errors)
- Wrong words = severity "critical"
- Pronunciation errors: "major" if score < 30, "minor" if 30-50
- Accept Indian English variations (th→t/d, v/w, r-coloring)
- Use simple, child-friendly language"""


def build_azure_analysis_prompt(azure_response: AzureRecognitionResult, reference_text: str) -> str:
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

    # Build the prompt - simplified for better Gemini reliability
    prompt = f"""Analyze pronunciation assessment for a child (age 5-7).

Expected: "{reference_text}"
Recognized: "{recognized_text}"

Azure Data:
{json.dumps(azure_dict, indent=2)}

Instructions:

1. EXTRACT SCORES from NBest[0].PronunciationAssessment:
   - pronunciation = PronScore
   - accuracy = AccuracyScore  
   - fluency = FluencyScore
   - completeness = CompletenessScore

2. FIND ALL PROBLEM WORDS:
   
   A. Check for wrong words (CRITICAL):
      - Compare expected "{reference_text}" with Words[].Word
      - If word doesn't match or ErrorType is "Substitution"/"Omission":
        * severity = "critical"
        * word = what they said
        * expected_sound = correct word
        * actual_sound = what they said
        * suggestion = "You said '[wrong]' but the word is '[correct]'"
   
   B. Check pronunciation (words with AccuracyScore < 50):
      - Skip Indian English variations (th→t/d, v/w confusion, r-coloring)
      - For each problem word:
        * severity = "major" if AccuracyScore < 30, else "minor"
        * word = the word
        * letter = problematic letter(s)
        * expected_sound = simple phoneme (æ→"a", ɪ→"i", ð→"th")
        * actual_sound = what they said (from NBestPhonemes[0])
        * suggestion = child-friendly tip

3. CREATE SUMMARY:
   - Perfect: "Wonderful! You said it perfectly!"
   - Good (>80): "Great job! Your pronunciation is excellent."
   - Multiple issues: "Good try! Let's practice a few words together."
   - One issue: "Great job! Let's work on one sound."

Return ALL problem words in word_level_feedback array."""

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
    print("\n" + "="*80)
    print("FULL GEMINI PROMPT:")
    print("="*80)
    if len(prompt) > 3000:
        print(prompt[:3000] + "\n...[TRUNCATED - Full length: " + str(len(prompt)) + " chars]...")
    else:
        print(prompt)
    print("="*80 + "\n")

    return prompt
