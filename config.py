"""Central configuration for the Pronunciation Assessment application."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Azure Speech Settings
    speech_key: str = Field(
        validation_alias=AliasChoices("SPEECH_KEY", "AZURE_SPEECH_KEY")
    )
    speech_region: str = Field(
        validation_alias=AliasChoices("SPEECH_REGION", "AZURE_SPEECH_REGION")
    )
    # Use a PA-supported locale by default; override via env if needed
    # Note: en-US is used because it provides phoneme-level details (NBestPhonemes, syllables)
    # which are required for word-level feedback. en-IN doesn't support these features.
    # The Gemini analysis is configured to be lenient with Indian English accents.
    speech_language_code: str = "en-US"

    # Gemini API Settings (for analysis only)
    gemini_api_key: str
    model_name: str
    assessment_temperature: float = 0.6
    # Higher default because thinking models can consume tokens before producing output
    assessment_max_output_tokens: int = 10000
