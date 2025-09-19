"""Central configuration and enums for the Pronunciation Assessment application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

# Load environment variables from the .env file once at import time.
load_dotenv()


class StreamlitMessageStyle(str, Enum):
    """Supported Streamlit message container styles."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    WRITE = "write"


class AudioMimeType(str, Enum):
    """Audio MIME types supported by the application."""

    WAV = "audio/wav"


class ModelResponseMimeType(str, Enum):
    """MIME types accepted for model responses."""

    TEXT = "text/plain"


class FileExtension(str, Enum):
    """File extensions used in the application."""

    WAV = ".wav"


class PageLayout(str, Enum):
    """Streamlit page layout options."""

    WIDE = "wide"


class ButtonType(str, Enum):
    """Button appearance variants."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"


@dataclass(frozen=True)
class GenerationSettings:
    """Configuration for a Gemini generation request."""

    temperature: float
    max_output_tokens: int
    response_mime_type: str


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    gemini_api_key: str
    model_name: str
    base_generation: GenerationSettings
    assessment_generation: GenerationSettings
    temp_file_extension: str
    recorded_audio_mime_type: str


def _require_env(name: str) -> str:
    """Fetch an environment variable, raising if it is missing."""

    value = os.getenv(name)
    if value is None:
        raise RuntimeError(
            f"Environment variable '{name}' is required but was not provided."
        )
    return value


def _env_as_float(name: str) -> float:
    """Fetch an environment variable as a float with error handling."""

    value = _require_env(name)
    try:
        return float(value)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable '{name}' must be a float, got '{value}'."
        ) from exc


def _env_as_int(name: str) -> int:
    """Fetch an environment variable as an int with error handling."""

    value = _require_env(name)
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable '{name}' must be an int, got '{value}'."
        ) from exc


def load_app_config() -> AppConfig:
    """Build the immutable configuration object sourced from the environment."""

    gemini_api_key = _require_env("GEMINI_API_KEY")
    model_name = _require_env("MODEL_NAME")

    base_generation = GenerationSettings(
        temperature=_env_as_float("MODEL_TEMPERATURE"),
        max_output_tokens=_env_as_int("MODEL_MAX_OUTPUT_TOKENS"),
        response_mime_type=_require_env("MODEL_RESPONSE_MIME_TYPE"),
    )

    assessment_generation = GenerationSettings(
        temperature=_env_as_float("ASSESSMENT_TEMPERATURE"),
        max_output_tokens=_env_as_int("ASSESSMENT_MAX_OUTPUT_TOKENS"),
        response_mime_type=_require_env("ASSESSMENT_RESPONSE_MIME_TYPE"),
    )

    temp_file_extension = _require_env("AUDIO_TEMP_FILE_EXTENSION")
    recorded_audio_mime_type = _require_env("RECORDED_AUDIO_MIME_TYPE")

    return AppConfig(
        gemini_api_key=gemini_api_key,
        model_name=model_name,
        base_generation=base_generation,
        assessment_generation=assessment_generation,
        temp_file_extension=temp_file_extension,
        recorded_audio_mime_type=recorded_audio_mime_type,
    )


APP_CONFIG = load_app_config()
"""Singleton instance containing the loaded configuration."""
