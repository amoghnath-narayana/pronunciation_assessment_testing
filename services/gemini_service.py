"""
Pronunciation Assessment Service - Main orchestrator for the assessment pipeline.

This service coordinates the complete pronunciation assessment workflow:
    [1] Receives audio bytes and expected text from API endpoint
    [2] Calls Azure Speech SDK for pronunciation scoring (async)
    [3] Sends Azure results to Gemini for learner-friendly analysis and word-level feedback
    [4] Optionally generates TTS audio narration from assessment results

Architecture:
    - Singleton pattern: One instance per app lifetime, initialized at startup
    - Async throughout: Azure SDK calls and TTS generation run non-blocking
    - Lazy TTS initialization: TTS composer only loads if optimization is enabled

Key Methods:
    - assess_pronunciation_async(): Main pipeline (steps 1-3)
    - generate_tts_narration_async(): Optional TTS generation (step 4)
    - _analyze_with_gemini(): Sends Azure results to Gemini for structured analysis
    - _parse_gemini_response(): Validates and parses Gemini's structured output

Performance Optimizations:
    - Async Azure Speech SDK calls (non-blocking I/O)
    - Async TTS generation allows parallel execution with other operations
    - High-score TTS caching (perfect pronunciation responses cached in memory)
    - TTS composer uses disk cache for dynamic narration segments
"""

import asyncio
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
    build_azure_analysis_prompt,
)
from services.azure_speech_service import assess_pronunciation_async
from utils import convert_audio


@dataclass
class AssessmentService:
    """
    Orchestrates pronunciation assessment: Azure → Gemini → TTS.

    This service is designed as a singleton (one instance per app lifetime).
    """

    config: AppConfig
    _composer: object = field(default=None, init=False, repr=False)
    _high_score_tts_cache: bytes = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize TTS composer for optimized audio generation."""
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
        """
        Initialize TTS composer with all required dependencies.

        Creates and wires together:
            - TTSAssetLoader: Loads pre-recorded audio clips from manifest
            - TTSCacheService: Manages disk cache for dynamic TTS segments
            - TTSNarrationComposer: Composes final audio from static + dynamic segments

        Returns:
            TTSNarrationComposer: Initialized composer ready for audio generation

        Raises:
            Exception: If initialization fails (caught in __post_init__)
        """
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
        Main assessment pipeline: Azure Speech → Gemini Analysis.

        Flow:
            [1] Validate inputs (audio bytes and reference text)
            [2] Call Azure Speech SDK for pronunciation assessment (async)
                - Returns RecognitionStatus, pronunciation scores, word-level data
                - Handles recognition failures (NoMatch, errors)
            [3] Extract Azure scores from response
                - PronScore, AccuracyScore, FluencyScore, CompletenessScore, ProsodyScore
                - Returns early with friendly message if recognition failed or scores are zero
            [4] Send Azure results to Gemini for learner-friendly analysis
                - Gemini generates summary_text, word_level_feedback, prosody_feedback
                - Uses structured output (JSON schema validation)

        Args:
            audio_data_bytes: Raw audio bytes (WAV/WebM format)
            expected_sentence_text: Reference sentence for pronunciation comparison

        Returns:
            AzureAnalysisResult: Contains summary_text, overall_scores, word_level_feedback, prosody_feedback

        Raises:
            AudioProcessingError: If audio/text is empty or Azure SDK fails
            InvalidAssessmentResponseError: If Gemini returns invalid structured output
        """
        # [1] Validate
        if not audio_data_bytes:
            raise AudioProcessingError("Audio data is empty")
        if not expected_sentence_text or not expected_sentence_text.strip():
            raise AudioProcessingError("Reference text is empty")

        logfire.info("Step 1: Starting assessment", audio_bytes=len(audio_data_bytes))

        # [2] Azure pronunciation assessment (async)
        azure_result = await assess_pronunciation_async(
            audio_bytes=audio_data_bytes,
            reference_text=expected_sentence_text,
            config=self.config,
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
        """
        Send Azure pronunciation results to Gemini for learner-friendly analysis.

        This method takes raw Azure Speech API results and sends them to Gemini
        for conversion into learner-friendly feedback with word-level suggestions.

        Flow:
            [1] Build prompt from Azure results and reference text
            [2] Call Gemini with structured output (response_schema=AzureAnalysisResult)
            [3] Parse and validate Gemini's structured response
            [4] Return validated AzureAnalysisResult

        Args:
            azure_result: Raw Azure Speech API response (dict with NBest, Words, scores)
            reference_text: Original reference sentence

        Returns:
            AzureAnalysisResult: Validated structured output from Gemini

        Raises:
            InvalidAssessmentResponseError: If Gemini returns invalid/missing structured output
            ValidationError: If Gemini's response doesn't match AzureAnalysisResult schema
        """
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
        Extract and validate Gemini's structured output.

        When response_schema is provided to Gemini, the client returns the structured
        object in response.parsed (no manual JSON parsing needed). This method:
            [1] Extracts response.parsed
            [2] Validates it matches AzureAnalysisResult schema
            [3] Logs detailed error info if parsing fails

        Args:
            response: Gemini API response with structured output

        Returns:
            AzureAnalysisResult: Validated assessment result

        Raises:
            InvalidAssessmentResponseError: If response.parsed is None or invalid
            ValidationError: If parsed data doesn't match AzureAnalysisResult schema
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

    async def generate_tts_narration_async(
        self, assessment_result: AzureAnalysisResult
    ) -> bytes:
        """
        Generate TTS audio narration from assessment result (async, non-blocking).

        This method creates audio feedback by composing pre-recorded clips with
        dynamically generated TTS for specific error corrections.

        Flow:
            [1] Check in-memory cache for high-score template response
            [2] If not cached, call TTS composer (runs in thread pool via asyncio.to_thread)
            [3] TTS composer builds audio:
                - Perfect reading: Single "perfect_intro" clip
                - Has errors: "needs_work_intro" + dynamic error TTS + "closing_cheer"
            [4] Cache high-score responses for future use

        Args:
            assessment_result: Assessment result containing summary_text and word_level_feedback

        Returns:
            bytes: WAV audio data, or None if TTS composer unavailable or generation fails

        Note:
            - Uses asyncio.to_thread for non-blocking execution
            - TTS composer handles disk caching for dynamic segments
            - High-score responses cached in memory (self._high_score_tts_cache)
        """
        # Check cache for high-score template response
        if (
            assessment_result.summary_text
            == "Excellent! Your pronunciation is perfect!"
            and self._high_score_tts_cache is not None
        ):
            logfire.info("Using cached high-score TTS")
            return self._high_score_tts_cache

        # Use asyncio.to_thread for non-blocking execution
        if self._composer:
            try:
                result = await asyncio.to_thread(
                    self._composer.compose, assessment_result
                )
            except Exception as e:
                logfire.error("TTS composer failed", error=str(e))
                return None
        else:
            logfire.warn("TTS composer not available")
            return None

        # Cache high-score TTS for future use
        if (
            assessment_result.summary_text
            == "Excellent! Your pronunciation is perfect!"
            and result is not None
        ):
            self._high_score_tts_cache = result
            logfire.info("Cached high-score TTS for future use")

        return result
