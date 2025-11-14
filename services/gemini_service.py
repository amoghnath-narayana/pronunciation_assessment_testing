"""Service layer for Gemini API interactions."""

import os
import tempfile
from dataclasses import dataclass
from functools import cached_property

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

    @cached_property
    def client(self):
        return genai.Client(api_key=self.config.gemini_api_key)

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
            return AssessmentResult.model_validate_json(response.text)

        except (ValueError, ValidationError) as e:
            st.error(f"Invalid assessment response: {e}")
        except Exception as e:
            st.error(f"Error during assessment: {e}")
        return None
