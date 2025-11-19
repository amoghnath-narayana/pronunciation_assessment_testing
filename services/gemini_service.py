"""Service layer for Gemini API interactions."""

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from google import genai
from google.genai import types
import logfire
from pydantic import ValidationError

from config import AppConfig
from exceptions import AudioUploadError, InvalidAssessmentResponseError
from models.assessment_models import AssessmentResult, get_gemini_response_schema
from prompts import SYSTEM_PROMPT, build_assessment_prompt, build_tts_narration_prompt
from utils import pcm_to_wav, temp_audio_file


@dataclass
class GeminiAssessmentService:
    config: AppConfig
    _composer: object = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize TTSNarrationComposer when tts_enable_optimization is True."""
        if self.config.tts_enable_optimization:
            try:
                self._composer = self._initialize_composer()
                logfire.info("TTS optimization enabled with composer")
            except Exception as e:
                logfire.warning(f"TTS optimization unavailable: {e}. Using fallback.")
                self._composer = None
        else:
            logfire.info("TTS optimization disabled, using legacy TTS")
            self._composer = None

    @cached_property
    def client(self):
        # Use v1alpha API for Gemini 3 features (thinking_level)
        return genai.Client(
            api_key=self.config.gemini_api_key,
            http_options={'api_version': 'v1alpha'}
        )

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
        
        # Initialize asset loader (will raise exception if initialization fails)
        asset_loader = TTSAssetLoader(
            manifest_path=Path(self.config.tts_manifest_path),
            assets_dir=Path(self.config.tts_assets_dir)
        )
        
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
        
        logfire.info("TTSNarrationComposer initialized successfully")
        return composer

    def _upload_audio_file(self, audio_data_bytes: bytes):
        """Upload WAV audio file to Gemini API using temporary file.

        Frontend sends 16kHz mono WAV audio optimized for speech recognition.
        No conversion needed - direct upload for best quality.

        Args:
            audio_data_bytes: WAV audio data from frontend

        Returns:
            Uploaded file object from Gemini API

        Raises:
            AudioUploadError: If audio upload fails
        """
        try:
            logfire.debug(f"Uploading {len(audio_data_bytes)} bytes of WAV audio to Gemini")

            with temp_audio_file(audio_data_bytes, self.config.temp_file_extension) as temp_path:
                return self.client.files.upload(
                    file=temp_path,
                    config=types.UploadFileConfig(
                        mime_type=self.config.recorded_audio_mime_type
                    )
                )

        except Exception as e:
            logfire.error(f"Audio upload failed: {e}")
            raise AudioUploadError(f"Failed to upload audio: {e}") from e

    def assess_pronunciation(self, audio_data_bytes: bytes, expected_sentence_text: str) -> AssessmentResult:
        """Assess pronunciation of audio against expected text.

        Args:
            audio_data_bytes: Audio data to assess
            expected_sentence_text: Expected sentence text

        Returns:
            AssessmentResult: Assessment result with scores and feedback

        Raises:
            AudioUploadError: If audio upload fails
            InvalidAssessmentResponseError: If response validation fails
            Exception: If API call fails
        """
        try:
            uploaded_file = self._upload_audio_file(audio_data_bytes)
            if not uploaded_file:
                logfire.error("Failed to upload audio file")
                raise AudioUploadError("Failed to upload audio file to Gemini API")

            # Gemini 3 thinking is ALWAYS ON (defaults to HIGH if not specified)
            # We explicitly set LOW for optimal latency while maintaining quality
            response = self.client.models.generate_content(
                model=self.config.model_name,
                contents=[build_assessment_prompt(expected_sentence_text), uploaded_file],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=self.config.assessment_temperature,
                    max_output_tokens=self.config.assessment_max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=get_gemini_response_schema(),
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                ),
            )
            result = AssessmentResult.model_validate_json(response.text)

            # Debug: Log errors from Gemini
            if result.specific_errors:
                logfire.info(f"Gemini detected {len(result.specific_errors)} errors: {[(e.word, e.issue) for e in result.specific_errors]}")

            return result

        except ValidationError as e:
            logfire.error(f"Invalid assessment response: {e}")
            raise InvalidAssessmentResponseError(f"Invalid assessment response: {e}") from e
        except AudioUploadError:
            raise
        except Exception as e:
            logfire.error(f"Error during assessment: {e}")
            raise

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
                logfire.debug("Using optimized TTS composer")
                return self._composer.compose(assessment_result)
            except Exception as e:
                logfire.warning(f"TTS composition failed: {e}. Using fallback.")

        # Fallback to legacy implementation
        logfire.debug("Using legacy TTS generation")
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
            logfire.error(f"Error generating TTS: {e}")
            return None
