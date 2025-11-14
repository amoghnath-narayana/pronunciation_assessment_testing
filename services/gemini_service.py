"""Service layer for Gemini API interactions."""

import os
import tempfile
from dataclasses import dataclass
from typing import Optional

import streamlit as st
from google import genai
from google.genai import types
from pydantic import ValidationError

from config import AppConfig
from models.assessment_models import AssessmentResult, get_gemini_response_schema
from prompts import SYSTEM_PROMPT, build_assessment_prompt


@dataclass
class GeminiAssessmentService:
    config: AppConfig

    def _upload_audio_file(self, audio_data_bytes: bytes):
        """Upload audio file using new SDK's Files API."""
        temp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=self.config.temp_file_extension
            ) as f:
                f.write(audio_data_bytes)
                temp_path = f.name
            # New SDK: client.files.upload()
            client = genai.Client(api_key=self.config.gemini_api_key)
            return client.files.upload(file=temp_path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _parse_assessment_response(self, response_text: str) -> AssessmentResult:
        """Parse assessment response as JSON."""
        return AssessmentResult.model_validate_json(response_text)

    def assess_pronunciation(
        self, audio_data_bytes: bytes, expected_sentence_text: str
    ) -> Optional[AssessmentResult]:
        try:
            uploaded_file = self._upload_audio_file(audio_data_bytes)
            if not uploaded_file:
                st.error("Failed to upload audio file")
                return None

            prompt = build_assessment_prompt(expected_sentence_text)
            assess_gen = self.config.assessment_generation

            # New SDK: Use types.GenerateContentConfig with proper ThinkingConfig
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=assess_gen.temperature,
                max_output_tokens=assess_gen.max_output_tokens,
                response_mime_type="application/json",
                response_schema=get_gemini_response_schema(),
                # Disable thinking mode for faster responses (10-30% speedup)
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )

            # Create content with prompt and uploaded file
            contents = [prompt, uploaded_file]

            # The model must generate complete valid JSON before returning
            client = genai.Client(api_key=self.config.gemini_api_key)
            response = client.models.generate_content(
                model=self.config.model_name, contents=contents, config=config
            )
            return self._parse_assessment_response(response.text)

        except ValueError as e:
            st.error(f"Unable to parse assessment response: {e}")
            return None
        except ValidationError as e:
            st.error(f"Invalid assessment data structure: {e}")
            return None
        except Exception as e:
            st.error(f"Error during assessment: {str(e)}")
            return None
