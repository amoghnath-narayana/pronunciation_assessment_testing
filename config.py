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
    speech_language_code: str = "en-US"
    speech_enable_miscue: bool = True

    # Gemini API Settings (for analysis and TTS only)
    gemini_api_key: str
    model_name: str
    assessment_temperature: float = 0.3
    # Higher default because thinking models can consume tokens before producing output
    assessment_max_output_tokens: int = 10000
    # Limit Gemini thinking depth (approx. "thinking level: low"); set None to use model default
    assessment_thinking_budget: int | None = 256

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
