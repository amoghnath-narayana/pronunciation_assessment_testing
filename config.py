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

    # TTS Optimization
    tts_assets_dir: str = "assets/tts"
    tts_manifest_path: str = "assets/tts/manifest.json"
    tts_cache_dir: str = "assets/tts/cache"
    tts_cache_size_mb: int = 500
    tts_enable_optimization: bool = True


APP_CONFIG = AppConfig()
