"""Central configuration for the Pronunciation Assessment application."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="forbid", env_prefix="")

    # Azure Speech Settings
    speech_key: str
    speech_region: str
    speech_language_code: str = "en-IN"

    # Gemini API Settings (for analysis and TTS only)
    gemini_api_key: str
    model_name: str
    assessment_temperature: float = 0.3
    assessment_max_output_tokens: int = 512

    # TTS Settings
    tts_model_name: str
    tts_voice_name: str
    tts_voice_style_prompt: str = "Speak warmly to a child."

    # TTS Optimization
    tts_assets_dir: str = "assets/tts"
    tts_manifest_path: str = "assets/tts/manifest.json"
    tts_cache_dir: str = "assets/tts/cache"
    tts_cache_size_mb: int = 500
    tts_enable_optimization: bool = True
