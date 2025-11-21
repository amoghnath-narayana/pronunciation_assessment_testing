"""
Assessment Service - Orchestrates the pronunciation assessment pipeline.

Flow:
    [1] Receive audio + expected text from API endpoint
    [2] Send to Azure Speech for pronunciation scores
    [3] Send to Gemini for learner-friendly feedback and word-level analysis
    [4] Generate TTS audio feedback (async, can run in parallel)

Optimizations:
    - Async Azure calls with Speech SDK
    - Singleton service pattern (initialized once at startup)
    - Async TTS generation for parallel execution (~300-500ms saved)
    - TTS caching for repeated responses
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from google import genai
from google.genai import types
import logfire
from pydantic import ValidationError

from config import AppConfig
from exceptions import AudioProcessingError, InvalidAssessmentResponseError
from models.assessment_models import (
    AzureAnalysisResult,
    OverallScores,
)
from prompts import (
    AZURE_ANALYSIS_SYSTEM_PROMPT,
    build_tts_narration_prompt,
    build_azure_analysis_prompt,
)
from services.azure_speech_service import assess_pronunciation_async, AzureSpeechConfig
from utils import pcm_to_wav


@dataclass
class AssessmentService:
    """
    Orchestrates pronunciation assessment: Azure → Gemini → TTS.

    This service is designed as a singleton (one instance per app lifetime).
    """

    config: AppConfig
    _composer: object = field(default=None, init=False, repr=False)
    _executor: ThreadPoolExecutor = field(default=None, init=False, repr=False)
    _high_score_tts_cache: bytes = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize TTS composer and thread pool for async operations."""
        # Thread pool for running sync Gemini calls in async context
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gemini")

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
            api_key=self.config.gemini_api_key, http_options={"api_version": "v1alpha"}
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
        return TTSNarrationComposer(
            asset_loader=asset_loader, cache_service=cache_service
        )

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
            [3] Call Gemini for friendly feedback and word-level analysis

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
            enable_miscue=self.config.speech_enable_miscue,
        )

        azure_result = await assess_pronunciation_async(
            audio_bytes=audio_data_bytes,
            reference_text=expected_sentence_text,
            language_code=self.config.speech_language_code,
            config=azure_config,
        )

        # Handle recognition failure
        recognition_status = azure_result.get("RecognitionStatus", "Unknown")
        display_text = azure_result.get("NBest", [{}])[0].get("Display", "") or ""
        logfire.info(
            f"Azure returned recognition | status={recognition_status} | display='{display_text[:120]}'"
        )
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

        accuracy = azure_scores.get("AccuracyScore", 0)
        fluency = azure_scores.get("FluencyScore", 0)
        completeness = azure_scores.get("CompletenessScore", 0)
        prosody = azure_scores.get("ProsodyScore", 0)
        word_count = len(nbest.get("Words", []))

        logfire.info(
            (
                f"Step 2 complete: Azure scores | pron={pron_score:.2f} "
                f"acc={accuracy:.2f} flu={fluency:.2f} comp={completeness:.2f} pros={prosody:.2f} "
                f"words={word_count}"
            )
        )

        # If Azure returned zeros (no evidence of scoring), don't send junk to Gemini
        non_zero_scores = [
            s for s in [pron_score, accuracy, fluency, completeness, prosody] if s
        ]
        if not non_zero_scores:
            logfire.warn(
                "Azure returned zero scores; treating as inaudible or assessment failure",
                display=display_text[:120],
                words=word_count,
            )
            return AzureAnalysisResult(
                summary_text="I couldn't hear you clearly. Please try again!",
                overall_scores=OverallScores(),
                word_level_feedback=[],
                prosody_feedback=None,
            )

        # [3] Call Gemini for learner-friendly feedback (always, to get word-level analysis)
        logfire.info("Step 3: Sending to Gemini for analysis")
        return self._analyze_with_gemini(azure_result, expected_sentence_text)

    def _analyze_with_gemini(
        self, azure_result: dict, reference_text: str
    ) -> AzureAnalysisResult:
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
                    response_schema=AzureAnalysisResult,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=self.config.assessment_thinking_budget
                    ),
                ),
            )

            result = self._parse_gemini_response(response)

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

    def _parse_gemini_response(
        self, response: types.GenerateContentResponse
    ) -> AzureAnalysisResult:
        """
        Parse Gemini structured output into AzureAnalysisResult.

        The Gemini client returns the structured object in `response.parsed` when
        `response_schema` is provided, so no manual JSON parsing is needed.
        """
        parsed = getattr(response, "parsed", None)
        text_preview = (getattr(response, "text", None) or "")[:300]
        candidates = getattr(response, "candidates", None) or []
        candidate_texts: list[str] = []
        candidate_details: list[dict] = []
        for cand in candidates:
            if not getattr(cand, "content", None):
                candidate_details.append(
                    {
                        "has_content": False,
                        "finish_reason": getattr(cand, "finish_reason", None),
                        "safety": getattr(cand, "safety_ratings", None),
                    }
                )
                continue

            parts = cand.content.parts or []
            parts_info = []
            for part in parts:
                parts_info.append(
                    {
                        "text": bool(getattr(part, "text", None)),
                        "function_call": bool(getattr(part, "function_call", None)),
                        "function_response": bool(
                            getattr(part, "function_response", None)
                        ),
                        "inline_data": bool(getattr(part, "inline_data", None)),
                    }
                )
                if part and getattr(part, "text", None):
                    candidate_texts.append(part.text[:200])

            candidate_details.append(
                {
                    "finish_reason": getattr(cand, "finish_reason", None),
                    "safety": getattr(cand, "safety_ratings", None),
                    "parts": parts_info,
                }
            )

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = (
            getattr(usage, "prompt_token_count", None) if usage is not None else None
        )
        candidate_tokens = (
            getattr(usage, "candidates_token_count", None)
            if usage is not None
            else None
        )
        finish_reasons = [getattr(c, "finish_reason", None) for c in candidates]

        if parsed is None:
            logfire.error(
                "Gemini returned no structured output",
                model=self.config.model_name,
                text_preview=text_preview,
                candidate_count=len(candidates),
                candidate_texts=candidate_texts,
                candidate_details=candidate_details,
                finish_reasons=finish_reasons,
                prompt_tokens=prompt_tokens,
                candidate_tokens=candidate_tokens,
            )
            logfire.debug("Gemini raw response", response_repr=repr(response))
            raise InvalidAssessmentResponseError("Gemini returned no structured output")

        if hasattr(parsed, "model_dump"):
            parsed = parsed.model_dump()

        try:
            return AzureAnalysisResult.model_validate(parsed)
        except ValidationError as e:
            logfire.error(
                "Invalid Gemini structured output",
                error=str(e),
                model=self.config.model_name,
                text_preview=text_preview,
                candidate_count=len(candidates),
                candidate_texts=candidate_texts,
                candidate_details=candidate_details,
                finish_reasons=finish_reasons,
                prompt_tokens=prompt_tokens,
                candidate_tokens=candidate_tokens,
            )
            raise InvalidAssessmentResponseError(
                f"Invalid Gemini structured output: {e}"
            ) from e

    def generate_tts_narration(self, assessment_result: AzureAnalysisResult) -> bytes:
        """Generate TTS audio from assessment result (sync version)."""
        if self._composer:
            try:
                return self._composer.compose(assessment_result)
            except Exception as e:
                logfire.warn("TTS composer failed, using fallback", error=str(e))

        return self._generate_tts_fallback(assessment_result)

    async def generate_tts_narration_async(
        self, assessment_result: AzureAnalysisResult
    ) -> bytes:
        """
        Generate TTS audio from assessment result (async version).

        Runs TTS generation in thread pool to avoid blocking the event loop.
        Uses cached audio for high-score responses.

        Args:
            assessment_result: The analysis result to narrate

        Returns:
            bytes: WAV audio data or None if generation fails
        """
        # Check cache for high-score template response
        if (
            assessment_result.summary_text
            == "Excellent! Your pronunciation is perfect!"
            and self._high_score_tts_cache is not None
        ):
            logfire.info("Using cached high-score TTS")
            return self._high_score_tts_cache

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor, self.generate_tts_narration, assessment_result
        )

        # Cache high-score TTS for future use
        if (
            assessment_result.summary_text
            == "Excellent! Your pronunciation is perfect!"
            and result is not None
        ):
            self._high_score_tts_cache = result
            logfire.info("Cached high-score TTS for future use")

        return result

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
