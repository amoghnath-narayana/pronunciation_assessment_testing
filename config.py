"""Central configuration and enums for the Pronunciation Assessment application."""

from __future__ import annotations

from enum import Enum
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


class GenerationSettings(BaseSettings):
    """Configuration for a Gemini generation request."""

    model_config = SettingsConfigDict(extra='forbid')

    temperature: float
    max_output_tokens: int
    response_mime_type: str


class AppConfig(BaseSettings):
    """Top-level application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='forbid'
    )

    gemini_api_key: str = Field(..., alias='GEMINI_API_KEY')
    model_name: str = Field(..., alias='MODEL_NAME')

    # Base generation settings
    model_temperature: float = Field(..., alias='MODEL_TEMPERATURE')
    model_max_output_tokens: int = Field(..., alias='MODEL_MAX_OUTPUT_TOKENS')
    model_response_mime_type: str = Field(..., alias='MODEL_RESPONSE_MIME_TYPE')

    # Assessment generation settings
    assessment_temperature: float = Field(..., alias='ASSESSMENT_TEMPERATURE')
    assessment_max_output_tokens: int = Field(..., alias='ASSESSMENT_MAX_OUTPUT_TOKENS')
    assessment_response_mime_type: str = Field(..., alias='ASSESSMENT_RESPONSE_MIME_TYPE')

    # Audio settings
    temp_file_extension: str = Field(..., alias='AUDIO_TEMP_FILE_EXTENSION')
    recorded_audio_mime_type: str = Field(..., alias='RECORDED_AUDIO_MIME_TYPE')

    @property
    def base_generation(self) -> GenerationSettings:
        """Get base generation settings."""
        return GenerationSettings(
            temperature=self.model_temperature,
            max_output_tokens=self.model_max_output_tokens,
            response_mime_type=self.model_response_mime_type,
        )

    @property
    def assessment_generation(self) -> GenerationSettings:
        """Get assessment generation settings."""
        return GenerationSettings(
            temperature=self.assessment_temperature,
            max_output_tokens=self.assessment_max_output_tokens,
            response_mime_type=self.assessment_response_mime_type,
        )


APP_CONFIG = AppConfig()
"""Singleton instance containing the loaded configuration."""
