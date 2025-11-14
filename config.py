"""Central configuration for the Pronunciation Assessment application."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid", env_prefix="")

    gemini_api_key: str
    model_name: str
    assessment_temperature: float
    assessment_max_output_tokens: int
    temp_file_extension: str
    recorded_audio_mime_type: str
    tts_model_name: str
    tts_voice_name: str
    tts_voice_style_prompt: str


APP_CONFIG = AppConfig()
