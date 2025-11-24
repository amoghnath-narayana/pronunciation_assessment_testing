"""Pronunciation Assessment Service - Main orchestrator."""

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
    get_azure_analysis_response_schema,
)
from prompts import AZURE_ANALYSIS_SYSTEM_PROMPT, build_azure_analysis_prompt
from services.azure_speech_service import assess_pronunciation_async


@dataclass
class AssessmentService:
    """Orchestrates pronunciation assessment: Azure → Gemini."""

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
        """Main assessment pipeline: Azure Speech SDK → Gemini Analysis."""
        # Validate inputs
        if not audio_data_bytes:
            raise AudioProcessingError("Audio data is empty")
        if not expected_sentence_text or not expected_sentence_text.strip():
            raise AudioProcessingError("Reference text is empty")

        logfire.info("Assessment started", audio_bytes=len(audio_data_bytes))

        # Get Azure pronunciation data
        azure_response = await assess_pronunciation_async(
            audio_bytes=audio_data_bytes,
            reference_text=expected_sentence_text,
            config=self.config,
        )

        # Handle failed/invalid recognition using Pydantic model methods
        if not azure_response.is_successful:
            logfire.warn("Recognition failed", status=azure_response.RecognitionStatus)
            return azure_response.get_fallback_result()

        if not azure_response.has_valid_scores:
            logfire.warn("Invalid scores received")
            return azure_response.get_fallback_result()

        # Log scores
        scores = azure_response.pronunciation_scores
        logfire.info(
            "Azure scores",
            pron=scores.PronScore,
            acc=scores.AccuracyScore,
            flu=scores.FluencyScore,
            comp=scores.CompletenessScore,
            words=len(azure_response.words),
        )

        # Analyze with Gemini
        return self._analyze_with_gemini(azure_response, expected_sentence_text)

    def _analyze_with_gemini(
        self, azure_response: AzureRecognitionResult, reference_text: str
    ) -> AzureAnalysisResult:
        """Send Azure results to Gemini for learner-friendly feedback."""
        try:
            response = self.client.models.generate_content(
                model=self.config.model_name,
                contents=build_azure_analysis_prompt(azure_response, reference_text),
                config=types.GenerateContentConfig(
                    system_instruction=AZURE_ANALYSIS_SYSTEM_PROMPT,
                    temperature=self.config.assessment_temperature,
                    max_output_tokens=self.config.assessment_max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=get_azure_analysis_response_schema(),
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )

            result = self._parse_gemini_response(response)
            
            logfire.info(
                "Gemini complete",
                tokens_in=response.usage_metadata.prompt_token_count,
                tokens_out=response.usage_metadata.candidates_token_count,
                feedback_count=len(result.word_level_feedback),
            )

            return result

        except ValidationError as e:
            logfire.error("Validation failed", errors=e.errors())
            raise InvalidAssessmentResponseError(f"Invalid response: {e}") from e
        except Exception as e:
            logfire.error("Gemini failed", error=str(e))
            raise InvalidAssessmentResponseError(f"Analysis failed: {e}") from e

    def _parse_gemini_response(
        self, response: types.GenerateContentResponse
    ) -> AzureAnalysisResult:
        """Extract and validate Gemini's structured output."""
        if not (parsed_data := getattr(response, "parsed", None)):
            raise InvalidAssessmentResponseError("No structured output from Gemini")

        # Convert Pydantic model to dict if needed
        if hasattr(parsed_data, "model_dump"):
            parsed_data = parsed_data.model_dump()

        return AzureAnalysisResult.model_validate(parsed_data)
