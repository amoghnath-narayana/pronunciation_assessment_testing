"""Central configuration for the Pronunciation Assessment application."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="forbid", env_prefix="")

    # Gemini API Settings
    gemini_api_key: str
    model_name: str
    assessment_temperature: float
    assessment_max_output_tokens: int

    # Audio Recording Settings
    temp_file_extension: str
    recorded_audio_mime_type: str
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    audio_bit_depth: int = 16

    # Voice Activity Detection (VAD) Settings
    vad_enabled: bool = True
    vad_positive_speech_threshold: float = 0.8
    vad_negative_speech_threshold: float = 0.4
    vad_min_speech_frames: int = 3
    vad_prespeech_pad_frames: int = 1
    vad_redemption_frames: int = 8
    vad_frame_samples: int = 1536
    vad_submit_user_speech_on_pause: bool = False

    # TTS Settings
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
