"""
Assessment Service - Orchestrates the pronunciation assessment pipeline.

Flow:
    [1] Receive audio + expected text from API endpoint
    [2] Send to Azure Speech for pronunciation scores
    [3] If score >= 90: Use template response (skip Gemini) - OPTIMIZATION
    [4] If score < 90: Send to Gemini for learner-friendly feedback
    [5] Generate TTS audio feedback

Optimizations:
    - Async Azure calls with connection pooling
    - High score shortcut skips Gemini (~500-1000ms saved)
    - Singleton service pattern (initialized once at startup)
"""

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from google import genai
from google.genai import types
import logfire
from pydantic import ValidationError

from config import AppConfig
from exceptions import AudioProcessingError, InvalidAssessmentResponseError
from models.assessment_models import AzureAnalysisResult, OverallScores, get_azure_analysis_response_schema
from prompts import AZURE_ANALYSIS_SYSTEM_PROMPT, build_tts_narration_prompt, build_azure_analysis_prompt
from services.azure_speech_service import assess_pronunciation_async, AzureSpeechConfig
from utils import pcm_to_wav

# High score threshold - skip Gemini for scores above this
HIGH_SCORE_THRESHOLD = 90


@dataclass
class AssessmentService:
    """
    Orchestrates pronunciation assessment: Azure → Gemini → TTS.

    This service is designed as a singleton (one instance per app lifetime).
    """

    config: AppConfig
    _composer: object = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize TTS composer if optimization is enabled."""
        if self.config.tts_enable_optimization:
            try:
                self._composer = self._initialize_composer()
                logfire.info("TTS composer initialized")
            except Exception as e:
                logfire.warn("TTS composer unavailable, using fallback", error=str(e))
                self._composer = None

    @cached_property
    def client(self):
        """Gemini API client (cached for service lifetime)."""
        return genai.Client(
            api_key=self.config.gemini_api_key,
            http_options={"api_version": "v1alpha"}
        )

    def _initialize_composer(self):
        """Initialize TTS composer with dependencies."""
        from services.tts_assets import TTSAssetLoader
        from services.tts_cache import TTSCacheService
        from services.tts_composer import TTSNarrationComposer

        asset_loader = TTSAssetLoader(
            manifest_path=Path(self.config.tts_manifest_path),
            assets_dir=Path(self.config.tts_assets_dir),
        )
        cache_service = TTSCacheService(
            cache_dir=Path(self.config.tts_cache_dir),
            cache_size_mb=self.config.tts_cache_size_mb,
            gemini_client=self.client,
            tts_config={
                "model_name": self.config.tts_model_name,
                "voice_name": self.config.tts_voice_name,
                "voice_style_prompt": self.config.tts_voice_style_prompt,
            },
        )
        return TTSNarrationComposer(asset_loader=asset_loader, cache_service=cache_service)

    async def assess_pronunciation_async(
        self,
        audio_data_bytes: bytes,
        expected_sentence_text: str,
    ) -> AzureAnalysisResult:
        """
        Step 1-4: Main assessment pipeline (async).

        Flow:
            [1] Validate inputs
            [2] Call Azure Speech API (async)
            [3] If score >= 90: Return template response (skip Gemini)
            [4] If score < 90: Call Gemini for friendly feedback

        Args:
            audio_data_bytes: Recorded audio (WAV/WebM)
            expected_sentence_text: Reference sentence

        Returns:
            AzureAnalysisResult: Scores and learner-friendly feedback
        """
        # [1] Validate
        if not audio_data_bytes:
            raise AudioProcessingError("Audio data is empty")
        if not expected_sentence_text or not expected_sentence_text.strip():
            raise AudioProcessingError("Reference text is empty")

        logfire.info("Step 1: Starting assessment", audio_bytes=len(audio_data_bytes))

        # [2] Azure pronunciation assessment (async)
        azure_config = AzureSpeechConfig(
            speech_key=self.config.speech_key,
            speech_region=self.config.speech_region,
            language_code=self.config.speech_language_code,
        )

        azure_result = await assess_pronunciation_async(
            audio_bytes=audio_data_bytes,
            reference_text=expected_sentence_text,
            language_code=self.config.speech_language_code,
            config=azure_config,
        )

        # Handle recognition failure
        recognition_status = azure_result.get("RecognitionStatus", "Unknown")
        if recognition_status != "Success":
            logfire.warn("Azure recognition failed", status=recognition_status)
            return AzureAnalysisResult(
                summary_text="I couldn't hear you clearly. Please try again!",
                overall_scores=OverallScores(),
                word_level_feedback=[],
                prosody_feedback=None,
            )

        # Extract Azure scores
        nbest = azure_result.get("NBest", [{}])[0]
        azure_scores = nbest.get("PronunciationAssessment", {})
        pron_score = azure_scores.get("PronScore", 0)

        logfire.info("Step 2 complete: Azure scores", pron=pron_score)

        # [3] HIGH SCORE SHORTCUT - Skip Gemini for excellent pronunciation
        if pron_score >= HIGH_SCORE_THRESHOLD:
            logfire.info(f"Step 3: High score ({pron_score}) - skipping Gemini")
            return self._build_high_score_response(azure_scores)

        # [4] Call Gemini for learner-friendly feedback
        logfire.info("Step 4: Sending to Gemini for analysis")
        return self._analyze_with_gemini(azure_result, expected_sentence_text)

    def _build_high_score_response(self, azure_scores: dict) -> AzureAnalysisResult:
        """
        Step 3: Build template response for high scores (skips Gemini).

        This saves ~500-1000ms by avoiding Gemini API call when
        the pronunciation is already excellent.

        Args:
            azure_scores: PronunciationAssessment dict from Azure

        Returns:
            AzureAnalysisResult: Pre-built encouraging response
        """
        return AzureAnalysisResult(
            summary_text="Excellent! Your pronunciation is perfect!",
            overall_scores=OverallScores(
                pronunciation=azure_scores.get("PronScore", 0),
                accuracy=azure_scores.get("AccuracyScore", 0),
                fluency=azure_scores.get("FluencyScore", 0),
                completeness=azure_scores.get("CompletenessScore", 0),
                prosody=azure_scores.get("ProsodyScore", 0),
            ),
            word_level_feedback=[],
            prosody_feedback=None,
        )

    def _analyze_with_gemini(self, azure_result: dict, reference_text: str) -> AzureAnalysisResult:
        """Send Azure results to Gemini for learner-friendly analysis."""
        try:
            prompt = build_azure_analysis_prompt(azure_result, reference_text)

            response = self.client.models.generate_content(
                model=self.config.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=AZURE_ANALYSIS_SYSTEM_PROMPT,
                    temperature=self.config.assessment_temperature,
                    max_output_tokens=self.config.assessment_max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=get_azure_analysis_response_schema(),
                ),
            )

            result = AzureAnalysisResult.model_validate_json(response.text)

            logfire.info(
                "Gemini analysis complete",
                prompt_tokens=response.usage_metadata.prompt_token_count,
                output_tokens=response.usage_metadata.candidates_token_count,
                feedback_items=len(result.word_level_feedback),
            )

            return result

        except ValidationError as e:
            logfire.error("Invalid Gemini response", error=str(e))
            raise InvalidAssessmentResponseError(f"Invalid Gemini response: {e}") from e
        except Exception as e:
            logfire.error("Gemini analysis failed", error=str(e))
            raise

    def generate_tts_narration(self, assessment_result: AzureAnalysisResult) -> bytes:
        """Generate TTS audio from assessment result."""
        if self._composer:
            try:
                return self._composer.compose(assessment_result)
            except Exception as e:
                logfire.warn("TTS composer failed, using fallback", error=str(e))

        return self._generate_tts_fallback(assessment_result)

    def _generate_tts_fallback(self, assessment_result: AzureAnalysisResult) -> bytes:
        """Fallback TTS generation."""
        try:
            narration_text = build_tts_narration_prompt(assessment_result)
            logfire.info("Generating TTS", text_length=len(narration_text))

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
                        wav_data = pcm_to_wav(part.inline_data.data)
                        logfire.info("TTS generated", audio_bytes=len(wav_data))
                        return wav_data

            logfire.warn("TTS returned no audio")
            return None

        except Exception as e:
            logfire.error("TTS generation failed", error=str(e))
            return None
