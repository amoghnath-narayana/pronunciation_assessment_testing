"""Central configuration for the Pronunciation Assessment application."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Azure Speech Settings
    speech_key: str
    speech_region: str
    speech_language_code: str

    # Gemini API Settings (for analysis only)
    gemini_api_key: str
    model_name: str
    assessment_temperature: float
    assessment_max_output_tokens: int
