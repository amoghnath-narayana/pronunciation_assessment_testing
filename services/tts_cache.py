"""Service for managing cached TTS audio with diskcache."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

import diskcache
from google import genai
from google.genai import types
import logfire

from utils import pcm_to_wav


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
                str(self.cache_dir),
                size_limit=size_limit_bytes
            )
            logfire.info(f"TTSCacheService initialized with cache_dir={self.cache_dir}, size_limit={self.cache_size_mb}MB")
        except Exception as e:
            logfire.error(f"Failed to initialize diskcache: {e}")
            self._cache = None

    def _generate_cache_key(self, text: str) -> str:
        """Create hash key from text + voice config.

        Args:
            text: The narration text to generate cache key for

        Returns:
            str: SHA256 hash of normalized text + voice_name
        """
        # Normalize text to improve cache hit rate
        # Strip whitespace and ensure consistent formatting
        normalized_text = text.strip()

        # Combine text with voice_name to ensure different voices get different cache entries
        voice_name = self.tts_config.get('voice_name', '')
        key_material = f"{normalized_text}|{voice_name}"

        # Generate SHA256 hash
        hash_obj = hashlib.sha256(key_material.encode('utf-8'))
        cache_key = hash_obj.hexdigest()

        logfire.debug(f"Generated cache key {cache_key[:8]}... for text: {text[:50]}...")
        return cache_key

    def get_or_generate(self, text: str) -> bytes:
        """Return cached WAV or generate via Gemini TTS.
        
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
        
        key = self._generate_cache_key(text)
        
        # Check cache first
        if key in self._cache:
            logfire.debug(f"Cache hit for key {key[:8]}...")
            return self._cache[key]
        
        # Cache miss - generate TTS
        logfire.debug(f"Cache miss, generating TTS for text: {text[:50]}...")
        wav_bytes = self._generate_tts(text)
        
        # Store in cache
        try:
            self._cache[key] = wav_bytes
            logfire.debug(f"Cached TTS audio for key {key[:8]}...")
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
            model_name = self.tts_config.get('model_name')
            voice_name = self.tts_config.get('voice_name')
            voice_style_prompt = self.tts_config.get('voice_style_prompt', '')
            
            # Combine voice style prompt with text
            full_prompt = f"{voice_style_prompt}\n\n{text}" if voice_style_prompt else text
            
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
                        wav_bytes = pcm_to_wav(part.inline_data.data)
                        logfire.info(f"Generated TTS audio: {len(wav_bytes)} bytes")
                        return wav_bytes
            
            raise Exception("No audio data in TTS response")
            
        except Exception as e:
            logfire.error(f"Error generating TTS: {e}")
            raise
