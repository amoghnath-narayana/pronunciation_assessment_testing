"""Application constants."""


# Audio Configuration
class AudioConfig:
    """Audio processing constants."""

    DEFAULT_SAMPLE_RATE = 24000
    DEFAULT_CHANNELS = 1
    DEFAULT_SAMPLE_WIDTH = 2  # 16-bit

    # File extensions
    WAV_EXTENSION = ".wav"
    MP3_EXTENSION = ".mp3"
    PCM_EXTENSION = ".pcm"


# API Configuration
class APIConfig:
    """API configuration constants."""

    VERSION = "1.0.0"
    TITLE = "Pronunciation Assessment API"
    DESCRIPTION = "API for assessing pronunciation using Google Gemini AI"

    # Default server settings
    DEFAULT_HOST = "0.0.0.0"
    DEFAULT_PORT = 8000


# TTS Configuration
class TTSConfig:
    """TTS-related constants."""

    TARGET_LOUDNESS_DBFS = -20.0
    CROSSFADE_DURATION_MS = 50

    # Cache settings
    DEFAULT_CACHE_SIZE_MB = 100
    CACHE_FILENAME = "tts_cache.json"
    MANIFEST_FILENAME = "manifest.json"
