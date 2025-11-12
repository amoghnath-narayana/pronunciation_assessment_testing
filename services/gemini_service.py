"""
Service layer for Gemini API interactions.

Handles all communication with the Google Gemini API for pronunciation assessment.
"""

import os
import tempfile
from typing import Optional
from json import JSONDecodeError

import streamlit as st
import google.generativeai as genai
from pydantic import ValidationError

from config import AppConfig
from models.assessment_models import AssessmentResult, get_gemini_response_schema
from prompts import SYSTEM_PROMPT, build_assessment_prompt


class GeminiAssessmentService:
    """Handles pronunciation assessment using Google's Gemini API."""

    def __init__(self, config: AppConfig):
        """
        Initialize the Gemini assessment service.

        Args:
            config: Application configuration containing API keys and settings
        """
        self.config = config
        self.model = self._initialize_model()

    def _initialize_model(self) -> genai.GenerativeModel:
        """
        Initialize the Gemini model with base configuration.

        Returns:
            Configured GenerativeModel instance
        """
        base_generation = self.config.base_generation

        generation_config = genai.GenerationConfig(
            temperature=base_generation.temperature,
            max_output_tokens=base_generation.max_output_tokens,
            response_mime_type=base_generation.response_mime_type,
        )

        return genai.GenerativeModel(
            model_name=self.config.model_name,
            system_instruction=SYSTEM_PROMPT,
            generation_config=generation_config,
        )

    def _upload_audio_file(self, audio_data_bytes: bytes):
        """
        Upload audio data to Gemini API.

        Args:
            audio_data_bytes: Audio data in bytes format

        Returns:
            Uploaded file reference or None if error
        """
        temp_audio_file_path: Optional[str] = None

        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=self.config.temp_file_extension
            ) as temp_audio_file:
                temp_audio_file.write(audio_data_bytes)
                temp_audio_file_path = temp_audio_file.name

            uploaded_file = genai.upload_file(temp_audio_file_path)
            return uploaded_file

        finally:
            if temp_audio_file_path and os.path.exists(temp_audio_file_path):
                os.unlink(temp_audio_file_path)

    def _parse_assessment_response(self, response_text: str) -> AssessmentResult:
        """
        Parse JSON response from the model into an AssessmentResult.

        Uses Pydantic's model_validate_json() for automatic parsing, validation,
        and type coercion. This eliminates the need for manual normalization.

        Args:
            response_text: Raw text response from the model

        Returns:
            Parsed and validated AssessmentResult

        Raises:
            ValueError: If JSON cannot be extracted from response
            ValidationError: If JSON doesn't match expected schema
        """
        # Extract JSON from response (model may include extra text)
        json_start_index = response_text.find("{")
        json_end_index = response_text.rfind("}")

        if json_start_index == -1 or json_end_index <= json_start_index:
            raise ValueError("Response does not contain a JSON object.")

        json_payload = response_text[json_start_index : json_end_index + 1]

        # Use Pydantic for automatic parsing, validation, and type coercion
        # This replaces ~79 lines of manual parsing and normalization code!
        return AssessmentResult.model_validate_json(json_payload)

    def assess_pronunciation(
        self, audio_data_bytes: bytes, expected_sentence_text: str
    ) -> Optional[AssessmentResult]:
        """
        Send audio to Gemini API for pronunciation assessment.

        Args:
            audio_data_bytes: Audio data in bytes format
            expected_sentence_text: The text the student should pronounce

        Returns:
            AssessmentResult or None if error occurs
        """
        try:
            # Upload audio file
            uploaded_audio_file = self._upload_audio_file(audio_data_bytes)
            if not uploaded_audio_file:
                st.error("Failed to upload audio file")
                return None

            # Build assessment prompt
            assessment_prompt = build_assessment_prompt(expected_sentence_text)

            # Configure assessment-specific generation settings
            assessment_generation = self.config.assessment_generation

            # Try using response_schema for native JSON mode (more efficient)
            # Falls back to text parsing if not supported
            try:
                generation_config = genai.GenerationConfig(
                    temperature=assessment_generation.temperature,
                    max_output_tokens=assessment_generation.max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=get_gemini_response_schema(),
                )
            except (TypeError, AttributeError):
                # Fallback: response_schema not supported in this Gemini version
                generation_config = genai.GenerationConfig(
                    temperature=assessment_generation.temperature,
                    max_output_tokens=assessment_generation.max_output_tokens,
                    response_mime_type=assessment_generation.response_mime_type,
                )

            # Generate assessment
            api_response = self.model.generate_content(
                [assessment_prompt, uploaded_audio_file],
                generation_config=generation_config,
            )

            # Parse and validate response using Pydantic
            # With response_schema, response is guaranteed valid JSON
            # Without it, we extract JSON from text response
            return self._parse_assessment_response(api_response.text)

        except (JSONDecodeError, ValueError) as parsing_error:
            st.error(f"Unable to parse assessment response: {parsing_error}")
            return None
        except ValidationError as validation_error:
            st.error(f"Invalid assessment data structure: {validation_error}")
            return None
        except Exception as error:
            st.error(f"Error during assessment: {str(error)}")
            return None
