"""Analyze token counts for system prompts."""

from prompts import SYSTEM_PROMPT, build_assessment_prompt

# For a rough token estimate, we'll use the approximation that 1 token ≈ 4 characters
# This is a common rule of thumb for English text

def estimate_tokens(text: str) -> dict:
    """Estimate token count using character and word counts."""
    chars = len(text)
    words = len(text.split())
    # Common approximations:
    # - 1 token ≈ 4 characters (for English)
    # - 1 token ≈ 0.75 words (more precise)
    tokens_by_chars = chars / 4
    tokens_by_words = words / 0.75

    return {
        "characters": chars,
        "words": words,
        "estimated_tokens_by_chars": int(tokens_by_chars),
        "estimated_tokens_by_words": int(tokens_by_words)
    }

print("=" * 80)
print("AUDIO ANALYSIS SYSTEM PROMPT")
print("=" * 80)
audio_analysis_stats = estimate_tokens(SYSTEM_PROMPT)
print(f"Characters: {audio_analysis_stats['characters']}")
print(f"Words: {audio_analysis_stats['words']}")
print(f"Estimated tokens (by chars/4): {audio_analysis_stats['estimated_tokens_by_chars']}")
print(f"Estimated tokens (by words/0.75): {audio_analysis_stats['estimated_tokens_by_words']}")
print(f"\nFirst 200 chars of prompt:")
print(SYSTEM_PROMPT[:200] + "...")

print("\n" + "=" * 80)
print("SAMPLE ASSESSMENT USER PROMPT (with example sentence)")
print("=" * 80)
sample_prompt = build_assessment_prompt("I have a red van")
sample_stats = estimate_tokens(sample_prompt)
print(f"Characters: {sample_stats['characters']}")
print(f"Words: {sample_stats['words']}")
print(f"Estimated tokens (by chars/4): {sample_stats['estimated_tokens_by_chars']}")
print(f"Estimated tokens (by words/0.75): {sample_stats['estimated_tokens_by_words']}")
print(f"\nFirst 300 chars of prompt:")
print(sample_prompt[:300] + "...")

print("\n" + "=" * 80)
print("TTS SYSTEM PROMPT")
print("=" * 80)
tts_prompt = "enthusiastic and encouraging tone for kids"
tts_stats = estimate_tokens(tts_prompt)
print(f"Characters: {tts_stats['characters']}")
print(f"Words: {tts_stats['words']}")
print(f"Estimated tokens (by chars/4): {tts_stats['estimated_tokens_by_chars']}")
print(f"Estimated tokens (by words/0.75): {tts_stats['estimated_tokens_by_words']}")
print(f"Full prompt: '{tts_prompt}'")

print("\n" + "=" * 80)
print("TOTAL CONTEXT FOR AUDIO ANALYSIS API CALL")
print("=" * 80)
total_chars = audio_analysis_stats['characters'] + sample_stats['characters']
total_words = audio_analysis_stats['words'] + sample_stats['words']
print(f"System prompt + User prompt combined:")
print(f"  Total characters: {total_chars}")
print(f"  Total words: {total_words}")
print(f"  Estimated tokens (by chars/4): {int(total_chars / 4)}")
print(f"  Estimated tokens (by words/0.75): {int(total_words / 0.75)}")
print(f"\n  Note: This excludes the audio file itself")
