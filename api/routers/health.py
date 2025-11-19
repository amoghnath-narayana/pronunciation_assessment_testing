"""Health check endpoint."""

from fastapi import APIRouter

from api_models import AudioConfigResponse, HealthCheckResponse
from config import AppConfig
from constants import APIConfig

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Check if the API is running and healthy.

    Returns:
        HealthCheckResponse: Service health status and version
    """
    return HealthCheckResponse(status="healthy", version=APIConfig.VERSION)


@router.get("/audio-config", response_model=AudioConfigResponse)
async def get_audio_config() -> AudioConfigResponse:
    """Get audio recording configuration for frontend.

    Returns:
        AudioConfigResponse: Audio configuration including sample rate, VAD settings
    """
    config = AppConfig()
    return AudioConfigResponse(
        sample_rate=config.audio_sample_rate,
        channels=config.audio_channels,
        bit_depth=config.audio_bit_depth,
        mime_type=config.recorded_audio_mime_type,
        vad_enabled=config.vad_enabled,
        vad_config={
            "positiveSpeechThreshold": config.vad_positive_speech_threshold,
            "negativeSpeechThreshold": config.vad_negative_speech_threshold,
            "minSpeechFrames": config.vad_min_speech_frames,
            "preSpeechPadFrames": config.vad_prespeech_pad_frames,
            "redemptionFrames": config.vad_redemption_frames,
            "frameSamples": config.vad_frame_samples,
            "submitUserSpeechOnPause": config.vad_submit_user_speech_on_pause,
        },
    )
