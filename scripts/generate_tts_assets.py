#!/usr/bin/env python3
"""Script to generate pre-recorded TTS audio clips for static narration segments.

This script generates 4 variations for each narration category using the Gemini TTS API,
normalizes loudness to -20 dBFS, and creates a manifest.json file for the TTSAssetLoader.

Usage:
    python scripts/generate_tts_assets.py
"""

import io
import json
import logging
import sys
import wave
from pathlib import Path
from typing import Dict, List

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from google import genai
from google.genai import types
from pydub import AudioSegment

from config import APP_CONFIG

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Target loudness for normalization (dBFS)
TARGET_LOUDNESS_DBFS = -20.0

# Number of variants to generate per category
VARIANTS_PER_CATEGORY = 4

# Category definitions with varied prompts
CATEGORY_PROMPTS = {
    "perfect_intro": {
        "intent": "Celebration for error-free reading",
        "prompts": [
            "Wow! That was perfect! You read every word correctly!",
            "Amazing job! You got everything right!",
            "Excellent! You read that perfectly!",
            "Fantastic! Every word was spot on!"
        ]
    },
    "needs_work_intro": {
        "intent": "Encouraging lead-in before corrections",
        "prompts": [
            "Good try! Let's work on a few things together.",
            "Nice effort! Here are some tips to help you improve.",
            "You're doing well! Let me help you with a couple of words.",
            "Great start! Let's practice these words a bit more."
        ]
    },
    "closing_cheer": {
        "intent": "Positive ending after corrections",
        "prompts": [
            "Keep practicing and you'll get even better!",
            "You're making great progress! Keep it up!",
            "Awesome work! You're improving every time!",
            "Great job! Keep reading and you'll be amazing!"
        ]
    }
}


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Convert raw PCM audio data to WAV format.
    
    Args:
        pcm_data: Raw PCM audio bytes
        sample_rate: Sample rate in Hz (default: 24000)
        channels: Number of audio channels (default: 1 for mono)
        sample_width: Sample width in bytes (default: 2 for 16-bit)
        
    Returns:
        bytes: WAV format audio data
    """
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return wav_buffer.getvalue()


def generate_tts_audio(client: genai.Client, text: str, voice_name: str, voice_style_prompt: str) -> bytes:
    """Generate TTS audio using Gemini API.
    
    Args:
        client: Gemini API client
        text: Text to synthesize
        voice_name: Voice name to use
        voice_style_prompt: Voice style prompt for tone/style control
        
    Returns:
        bytes: WAV format audio data
        
    Raises:
        Exception: If TTS generation fails
    """
    try:
        # Combine voice style prompt with text
        full_prompt = f"{voice_style_prompt}\n\n{text}"
        
        logger.info(f"Generating TTS for: {text[:50]}...")
        
        response = client.models.generate_content(
            model=APP_CONFIG.tts_model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                ),
            ),
        )
        
        # Extract PCM audio data and convert to WAV
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    wav_bytes = pcm_to_wav(part.inline_data.data)
                    logger.info(f"Generated {len(wav_bytes)} bytes of audio")
                    return wav_bytes
        
        raise Exception("No audio data in TTS response")
        
    except Exception as e:
        logger.error(f"Error generating TTS: {e}")
        raise


def normalize_loudness(audio_segment: AudioSegment, target_dbfs: float = TARGET_LOUDNESS_DBFS) -> AudioSegment:
    """Normalize audio loudness to target dBFS level.
    
    Args:
        audio_segment: pydub AudioSegment to normalize
        target_dbfs: Target loudness in dBFS (default: -20.0)
        
    Returns:
        AudioSegment: Normalized audio
    """
    # Calculate change needed to reach target
    change_in_dbfs = target_dbfs - audio_segment.dBFS
    
    # Apply gain adjustment
    normalized = audio_segment.apply_gain(change_in_dbfs)
    
    logger.debug(f"Normalized audio from {audio_segment.dBFS:.2f} dBFS to {normalized.dBFS:.2f} dBFS")
    
    return normalized


def generate_category_variants(
    client: genai.Client,
    category: str,
    prompts: List[str],
    output_dir: Path,
    voice_name: str,
    voice_style_prompt: str
) -> List[str]:
    """Generate all variants for a category.
    
    Args:
        client: Gemini API client
        category: Category name (e.g., "perfect_intro")
        prompts: List of text prompts to generate
        output_dir: Directory to save audio files
        voice_name: Voice name to use
        voice_style_prompt: Voice style prompt
        
    Returns:
        List[str]: List of relative file paths for generated variants
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    variant_paths = []
    
    for i, prompt_text in enumerate(prompts, start=1):
        try:
            # Generate TTS audio
            wav_bytes = generate_tts_audio(client, prompt_text, voice_name, voice_style_prompt)
            
            # Load into pydub for normalization
            audio_segment = AudioSegment.from_wav(io.BytesIO(wav_bytes))
            
            # Normalize loudness
            normalized_audio = normalize_loudness(audio_segment)
            
            # Export to file
            variant_filename = f"variant_{i}.wav"
            variant_path = output_dir / variant_filename
            normalized_audio.export(str(variant_path), format="wav")
            
            # Store relative path for manifest
            relative_path = f"{category}/{variant_filename}"
            variant_paths.append(relative_path)
            
            logger.info(f"Saved {category} variant {i} to {variant_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate {category} variant {i}: {e}")
            raise
    
    return variant_paths


def create_manifest(categories_data: Dict[str, Dict], output_path: Path, voice_name: str):
    """Create manifest.json file with category definitions.
    
    Args:
        categories_data: Dictionary mapping category names to their data
        output_path: Path to save manifest.json
        voice_name: Voice name used for generation
    """
    manifest = {
        "version": "1.0",
        "voice_name": voice_name,
        "categories": {}
    }
    
    for category, data in categories_data.items():
        manifest["categories"][category] = {
            "intent": data["intent"],
            "variants": data["variants"]
        }
    
    # Write manifest file
    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    logger.info(f"Created manifest at {output_path}")


def main():
    """Main execution function."""
    logger.info("Starting TTS asset generation")
    logger.info(f"Configuration: model={APP_CONFIG.tts_model_name}, voice={APP_CONFIG.tts_voice_name}")
    
    # Initialize Gemini client
    client = genai.Client(api_key=APP_CONFIG.gemini_api_key)
    
    # Base directory for TTS assets
    assets_base_dir = Path(APP_CONFIG.tts_assets_dir)
    assets_base_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate variants for each category
    categories_data = {}
    
    for category, config in CATEGORY_PROMPTS.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"Generating category: {category}")
        logger.info(f"Intent: {config['intent']}")
        logger.info(f"{'='*60}")
        
        category_dir = assets_base_dir / category
        
        variant_paths = generate_category_variants(
            client=client,
            category=category,
            prompts=config["prompts"],
            output_dir=category_dir,
            voice_name=APP_CONFIG.tts_voice_name,
            voice_style_prompt=APP_CONFIG.tts_voice_style_prompt
        )
        
        categories_data[category] = {
            "intent": config["intent"],
            "variants": variant_paths
        }
        
        logger.info(f"Completed {category}: {len(variant_paths)} variants generated")
    
    # Create manifest.json
    manifest_path = Path(APP_CONFIG.tts_manifest_path)
    create_manifest(categories_data, manifest_path, APP_CONFIG.tts_voice_name)
    
    logger.info("\n" + "="*60)
    logger.info("TTS asset generation complete!")
    logger.info(f"Assets saved to: {assets_base_dir}")
    logger.info(f"Manifest saved to: {manifest_path}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
