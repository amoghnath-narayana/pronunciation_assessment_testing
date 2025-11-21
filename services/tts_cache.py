"""Service for managing cached TTS audio with diskcache."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

import diskcache
from google import genai
from google.genai import types
import logfire

from utils import convert_audio


@dataclass
class TTSCacheService:
    """Manages cached TTS audio with diskcache."""

    cache_dir: Path
    cache_size_mb: int
    gemini_client: genai.Client
    tts_config: Dict  # model_name, voice_name, voice_style_prompt
    _cache: diskcache.Cache = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize diskcache.Cache with cache_dir and size_limit parameters."""
        try:
            # Ensure cache directory exists
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Initialize diskcache with size limit in bytes
            size_limit_bytes = self.cache_size_mb * 1024 * 1024
            self._cache = diskcache.Cache(
                str(self.cache_dir), size_limit=size_limit_bytes
            )
            logfire.info(
                f"TTSCacheService initialized with cache_dir={self.cache_dir}, size_limit={self.cache_size_mb}MB"
            )
        except Exception as e:
            logfire.error(f"Failed to initialize diskcache: {e}")
            self._cache = None

    def get_or_generate(self, text: str) -> bytes:
        """Return cached WAV or generate via Gemini TTS.

        Uses diskcache's built-in key handling (no manual hashing needed).

        Args:
            text: The narration text to synthesize

        Returns:
            bytes: WAV audio data

        Raises:
            Exception: If TTS generation fails and no cached version exists
        """
        if self._cache is None:
            logfire.warning("Cache not available, generating TTS directly")
            return self._generate_tts(text)

        # Use tuple as cache key - diskcache handles serialization
        voice_name = self.tts_config.get("voice_name", "")
        cache_key = (text.strip(), voice_name)

        # Check cache first
        if cache_key in self._cache:
            logfire.debug(f"Cache hit for text: {text[:50]}...")
            return self._cache[cache_key]

        # Cache miss - generate TTS
        logfire.debug(f"Cache miss, generating TTS for text: {text[:50]}...")
        wav_bytes = self._generate_tts(text)

        # Store in cache
        try:
            self._cache[cache_key] = wav_bytes
            logfire.debug(f"Cached TTS audio for text: {text[:50]}...")
        except Exception as e:
            logfire.warning(f"Failed to cache TTS audio: {e}")

        return wav_bytes

    def _generate_tts(self, text: str) -> bytes:
        """Call Gemini TTS API and convert to WAV.

        This method extracts the current Gemini TTS API call logic
        from GeminiAssessmentService.generate_tts_narration.

        Args:
            text: The narration text to synthesize

        Returns:
            bytes: WAV audio data

        Raises:
            Exception: If TTS generation fails
        """
        try:
            model_name = self.tts_config.get("model_name")
            voice_name = self.tts_config.get("voice_name")
            voice_style_prompt = self.tts_config.get("voice_style_prompt", "")

            # Combine voice style prompt with text
            full_prompt = (
                f"{voice_style_prompt}\n\n{text}" if voice_style_prompt else text
            )

            response = self.gemini_client.models.generate_content(
                model=model_name,
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
                        wav_bytes = convert_audio(
                            part.inline_data.data,
                            output_format="wav",
                            sample_rate=24000,
                            channels=1,
                            is_raw_pcm=True,
                        )
                        logfire.info(f"Generated TTS audio: {len(wav_bytes)} bytes")
                        return wav_bytes

            raise Exception("No audio data in TTS response")

        except Exception as e:
            logfire.error(f"Error generating TTS: {e}")
            raise
