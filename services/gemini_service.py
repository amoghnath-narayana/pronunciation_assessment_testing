"""Service layer for Gemini API interactions."""

import io
import logging
import os
import tempfile
import wave
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import streamlit as st
from google import genai
from google.genai import types
from pydantic import ValidationError

from config import AppConfig
from models.assessment_models import AssessmentResult, get_gemini_response_schema
from prompts import SYSTEM_PROMPT, build_assessment_prompt, build_tts_narration_prompt

logger = logging.getLogger(__name__)


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Convert raw PCM audio data to WAV format."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return wav_buffer.getvalue()


@dataclass
class GeminiAssessmentService:
    config: AppConfig
    _composer: object = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize TTSNarrationComposer when tts_enable_optimization is True."""
        if self.config.tts_enable_optimization:
            try:
                self._composer = self._initialize_composer()
                logger.info("TTS optimization enabled with composer")
            except Exception as e:
                logger.warning(f"TTS optimization unavailable: {e}. Using fallback.")
                st.warning(f"TTS optimization unavailable: {e}. Using fallback.")
                self._composer = None
        else:
            logger.info("TTS optimization disabled, using legacy TTS")
            self._composer = None

    @cached_property
    def client(self):
        return genai.Client(api_key=self.config.gemini_api_key)

    def _initialize_composer(self):
        """Initialize TTSNarrationComposer with dependencies.
        
        Instantiates TTSAssetLoader, TTSCacheService, and TTSNarrationComposer
        with configuration from AppConfig.
        
        Returns:
            TTSNarrationComposer: Initialized composer instance
            
        Raises:
            Exception: If initialization fails (e.g., missing assets)
        """
        from services.tts_assets import TTSAssetLoader
        from services.tts_cache import TTSCacheService
        from services.tts_composer import TTSNarrationComposer
        
        # Initialize asset loader
        asset_loader = TTSAssetLoader(
            manifest_path=Path(self.config.tts_manifest_path),
            assets_dir=Path(self.config.tts_assets_dir)
        )
        
        # Verify assets loaded successfully
        if not asset_loader.is_available():
            raise Exception("TTSAssetLoader failed to load assets")
        
        # Initialize cache service
        cache_service = TTSCacheService(
            cache_dir=Path(self.config.tts_cache_dir),
            cache_size_mb=self.config.tts_cache_size_mb,
            gemini_client=self.client,
            tts_config={
                "model_name": self.config.tts_model_name,
                "voice_name": self.config.tts_voice_name,
                "voice_style_prompt": self.config.tts_voice_style_prompt
            }
        )
        
        # Initialize composer
        composer = TTSNarrationComposer(
            asset_loader=asset_loader,
            cache_service=cache_service
        )
        
        logger.info("TTSNarrationComposer initialized successfully")
        return composer

    def _upload_audio_file(self, audio_data_bytes: bytes):
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=self.config.temp_file_extension
            ) as f:
                f.write(audio_data_bytes)
                temp_path = f.name
            return self.client.files.upload(file=temp_path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def assess_pronunciation(self, audio_data_bytes: bytes, expected_sentence_text: str):
        try:
            uploaded_file = self._upload_audio_file(audio_data_bytes)
            if not uploaded_file:
                st.error("Failed to upload audio file")
                return None

            response = self.client.models.generate_content(
                model=self.config.model_name,
                contents=[build_assessment_prompt(expected_sentence_text), uploaded_file],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=self.config.assessment_temperature,
                    max_output_tokens=self.config.assessment_max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=get_gemini_response_schema(),
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            result = AssessmentResult.model_validate_json(response.text)

            # Debug: Log errors from Gemini
            if result.specific_errors:
                logger.info(f"Gemini detected {len(result.specific_errors)} errors: {[(e.word, e.issue) for e in result.specific_errors]}")

            return result

        except (ValueError, ValidationError) as e:
            st.error(f"Invalid assessment response: {e}")
        except Exception as e:
            st.error(f"Error during assessment: {e}")
        return None

    def generate_tts_narration(self, assessment_result: AssessmentResult) -> bytes:
        """Generate TTS audio from assessment result.
        
        Uses optimized composer path if available, otherwise falls back to legacy
        single-call TTS generation.
        
        Args:
            assessment_result: The assessment result to generate narration for
            
        Returns:
            bytes: WAV audio data, or None if generation fails
        """
        # Use optimized path if composer is available
        if self._composer:
            try:
                logger.debug("Using optimized TTS composer")
                return self._composer.compose(assessment_result)
            except Exception as e:
                logger.warning(f"TTS composition failed: {e}. Using fallback.")
                st.warning(f"TTS composition failed: {e}. Using fallback.")
        
        # Fallback to legacy implementation
        logger.debug("Using legacy TTS generation")
        return self._generate_tts_legacy(assessment_result)

    def _generate_tts_legacy(self, assessment_result: AssessmentResult) -> bytes:
        """Original single-call TTS generation (current implementation).
        
        This method preserves the original monolithic TTS approach as a fallback
        when the optimized composer is unavailable or fails.
        
        Args:
            assessment_result: The assessment result to generate narration for
            
        Returns:
            bytes: WAV audio data, or None if generation fails
        """
        try:
            narration_text = build_tts_narration_prompt(assessment_result)

            response = self.client.models.generate_content(
                model=self.config.tts_model_name,
                contents=f"{self.config.tts_voice_style_prompt}\n\n{narration_text}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=self.config.tts_voice_name
                            )
                        )
                    ),
                ),
            )

            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        return pcm_to_wav(part.inline_data.data)

        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            st.error(f"Error generating TTS: {e}")
        return None
