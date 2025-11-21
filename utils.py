"""Utility functions for the Pronunciation Assessment Application."""

import io

from pydub import AudioSegment


def pcm_to_wav(
    pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2
) -> bytes:
    """Convert raw PCM audio data to WAV format.

    Used for converting Gemini TTS output (raw PCM) to WAV format.

    Args:
        pcm_data: Raw PCM audio bytes from Gemini TTS
        sample_rate: Audio sample rate in Hz (default: 24000 for Gemini TTS)
        channels: Number of audio channels (default: 1 for mono)
        sample_width: Sample width in bytes (default: 2 for 16-bit)

    Returns:
        bytes: WAV format audio data
    """
    audio = AudioSegment(
        data=pcm_data,
        sample_width=sample_width,
        frame_rate=sample_rate,
        channels=channels,
    )
    buffer = io.BytesIO()
    audio.export(buffer, format="wav")
    return buffer.getvalue()
