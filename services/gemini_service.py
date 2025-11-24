"""
Pronunciation Assessment Service - Main orchestrator.

Coordinates the assessment pipeline:
    [1] Validate inputs (audio + text)
    [2] Get pronunciation data from Azure Speech SDK (AzureRecognitionResult)
    [3] Send to Gemini for learner-friendly feedback (AzureAnalysisResult)

Architecture:
    - Singleton pattern (one instance per app lifetime)
    - Async throughout (non-blocking Azure SDK calls)
    - Pydantic models for type safety and validation

Methods:
    - assess_pronunciation_async(): Main pipeline
    - _analyze_with_gemini(): Convert Azure data to friendly feedback via Gemini
    - _parse_gemini_response(): Validate Gemini's structured output
"""

from dataclasses import dataclass
from functools import cached_property

from google import genai
from google.genai import types
import logfire
from pydantic import ValidationError

from config import AppConfig
from exceptions import AudioProcessingError, InvalidAssessmentResponseError
from models.assessment_models import (
    AzureAnalysisResult,
    AzureRecognitionResult,
    OverallScores,
)
from prompts import (
    AZURE_ANALYSIS_SYSTEM_PROMPT,
    build_azure_analysis_prompt,
)
from services.azure_speech_service import assess_pronunciation_async


@dataclass
class AssessmentService:
    """
    Orchestrates pronunciation assessment: Azure → Gemini.

    This service is designed as a singleton (one instance per app lifetime).
    """

    config: AppConfig

    @cached_property
    def client(self):
        """Gemini API client (cached for service lifetime)."""
        return genai.Client(
            api_key=self.config.gemini_api_key, http_options={"api_version": "v1alpha"}
        )

    async def assess_pronunciation_async(
        self,
        audio_data_bytes: bytes,
        expected_sentence_text: str,
    ) -> AzureAnalysisResult:
        """
        Main assessment pipeline: Azure Speech SDK → Gemini Analysis.

        Flow:
            [1] Validate inputs
            [2] Get pronunciation data from Azure (returns AzureRecognitionResult)
            [3] Check if recognition successful and scores are valid
            [4] Send Azure data to Gemini for learner-friendly feedback

        Args:
            audio_data_bytes: Raw audio (WAV/WebM)
            expected_sentence_text: Reference text for comparison

        Returns:
            AzureAnalysisResult: Friendly feedback with scores and word-level suggestions

        Raises:
            AudioProcessingError: Empty audio/text or Azure failure
            InvalidAssessmentResponseError: Invalid Gemini response
        """
        # [1] Validate
        if not audio_data_bytes:
            raise AudioProcessingError("Audio data is empty")
        if not expected_sentence_text or not expected_sentence_text.strip():
            raise AudioProcessingError("Reference text is empty")

        logfire.info("Assessment pipeline started", audio_bytes=len(audio_data_bytes))

        # [2] Get pronunciation data from Azure
        azure_response = await assess_pronunciation_async(
            audio_bytes=audio_data_bytes,
            reference_text=expected_sentence_text,
            config=self.config,
        )

        # [3] Handle unsuccessful recognition
        if not azure_response.is_successful:
            logfire.warn(
                "Azure recognition unsuccessful",
                status=azure_response.RecognitionStatus
            )
            return AzureAnalysisResult(
                summary_text="I couldn't hear you clearly. Please try again!",
                overall_scores=OverallScores(),
                word_level_feedback=[],
            )

        # Extract scores using Pydantic model properties
        scores = azure_response.pronunciation_scores
        words = azure_response.words

        if not scores:
            logfire.warn("Azure returned no pronunciation scores")
            return AzureAnalysisResult(
                summary_text="I couldn't hear you clearly. Please try again!",
                overall_scores=OverallScores(),
                word_level_feedback=[],
            )

        logfire.info(
            "Azure scores received",
            pronunciation=scores.PronScore,
            accuracy=scores.AccuracyScore,
            fluency=scores.FluencyScore,
            completeness=scores.CompletenessScore,
            word_count=len(words)
        )

        # Check for all-zero scores (unexpected)
        if all(s in (0, None) for s in [scores.PronScore, scores.AccuracyScore, scores.FluencyScore]):
            logfire.warn("Azure returned all-zero scores")
            return AzureAnalysisResult(
                summary_text="I couldn't hear you clearly. Please try again!",
                overall_scores=OverallScores(),
                word_level_feedback=[],
            )

        # [4] Send to Gemini for learner-friendly analysis
        logfire.info("Sending to Gemini for analysis")
        return self._analyze_with_gemini(azure_response, expected_sentence_text)

    def _analyze_with_gemini(
        self, azure_response: AzureRecognitionResult, reference_text: str
    ) -> AzureAnalysisResult:
        """
        Send Azure results to Gemini for learner-friendly feedback.

        Uses Gemini's structured output with Pydantic schema validation.

        Args:
            azure_response: Validated Azure recognition result (Pydantic model)
            reference_text: Expected text

        Returns:
            AzureAnalysisResult: Learner-friendly feedback with word-level suggestions

        Raises:
            InvalidAssessmentResponseError: Invalid/missing Gemini response
        """
        try:
            prompt = build_azure_analysis_prompt(azure_response, reference_text)

            response = self.client.models.generate_content(
                model=self.config.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=AZURE_ANALYSIS_SYSTEM_PROMPT,
                    temperature=self.config.assessment_temperature,
                    max_output_tokens=self.config.assessment_max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=AzureAnalysisResult,
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )

            # Log raw response for debugging
            parsed_raw = getattr(response, "parsed", None)
            logfire.debug(
                "Gemini raw response received",
                has_parsed=parsed_raw is not None,
                parsed_preview=str(parsed_raw)[:500] if parsed_raw else None,
            )

            result = self._parse_gemini_response(response)

            logfire.info(
                "Gemini analysis complete",
                prompt_tokens=response.usage_metadata.prompt_token_count,
                output_tokens=response.usage_metadata.candidates_token_count,
                feedback_items=len(result.word_level_feedback),
            )

            # Log full Gemini response for debugging
            import json
            print("\n" + "="*80)
            print("GEMINI RESPONSE JSON:")
            print("="*80)
            print(json.dumps(result.model_dump(), indent=2))
            print("="*80 + "\n")

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

        With response_schema, Gemini SDK handles parsing automatically via response.parsed.
        Pydantic validates the structure - we just need to extract and validate.

        Args:
            response: Gemini API response with structured output

        Returns:
            AzureAnalysisResult: Validated assessment result

        Raises:
            InvalidAssessmentResponseError: If response.parsed is missing or invalid
        """
        parsed_data = getattr(response, "parsed", None)

        if parsed_data is None:
            # Safe text extraction (handle None case)
            response_text = getattr(response, "text", None) or ""
            logfire.error(
                "Gemini returned no structured output",
                model=self.config.model_name,
                response_text_preview=response_text[:200],
            )
            raise InvalidAssessmentResponseError("Gemini returned no structured output")

        # Convert to dict if it's a Pydantic model
        if hasattr(parsed_data, "model_dump"):
            parsed_data = parsed_data.model_dump()

        # Validate with Pydantic
        try:
            return AzureAnalysisResult.model_validate(parsed_data)
        except ValidationError as e:
            logfire.error(
                "Gemini response validation failed",
                error=str(e),
                validation_errors=e.errors(),
                parsed_data_preview=str(parsed_data)[:500],
            )
            raise InvalidAssessmentResponseError(
                f"Invalid Gemini response structure: {e.errors()}"
            ) from e


