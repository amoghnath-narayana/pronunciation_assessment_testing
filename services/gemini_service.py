"""Service layer for Gemini API interactions."""

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

    def __init__(self, config: AppConfig):
        self.config = config
        self.model = self._initialize_model()

    def _initialize_model(self) -> genai.GenerativeModel:
        base_gen = self.config.base_generation
        return genai.GenerativeModel(
            model_name=self.config.model_name,
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=base_gen.temperature,
                max_output_tokens=base_gen.max_output_tokens,
                response_mime_type=base_gen.response_mime_type,
            ),
        )

    def _upload_audio_file(self, audio_data_bytes: bytes):
        temp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=self.config.temp_file_extension
            ) as f:
                f.write(audio_data_bytes)
                temp_path = f.name
            return genai.upload_file(temp_path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _parse_assessment_response(self, response_text: str) -> AssessmentResult:
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("Response does not contain a JSON object.")
        return AssessmentResult.model_validate_json(response_text[start : end + 1])

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

            try:
                gen_config = genai.GenerationConfig(
                    temperature=assess_gen.temperature,
                    max_output_tokens=assess_gen.max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=get_gemini_response_schema(),
                )
            except (TypeError, AttributeError):
                gen_config = genai.GenerationConfig(
                    temperature=assess_gen.temperature,
                    max_output_tokens=assess_gen.max_output_tokens,
                    response_mime_type=assess_gen.response_mime_type,
                )

            response = self.model.generate_content([prompt, uploaded_file], generation_config=gen_config)
            return self._parse_assessment_response(response.text)

        except (JSONDecodeError, ValueError) as e:
            st.error(f"Unable to parse assessment response: {e}")
            return None
        except ValidationError as e:
            st.error(f"Invalid assessment data structure: {e}")
            return None
        except Exception as e:
            st.error(f"Error during assessment: {str(e)}")
            return None
