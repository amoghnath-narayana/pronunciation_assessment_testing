"""Utility functions for the Pronunciation Assessment Application."""

import io

from pydub import AudioSegment


def convert_audio(
    audio_data: bytes,
    output_format: str = "wav",
    sample_rate: int | None = None,
    channels: int | None = None,
    sample_width: int | None = None,
    is_raw_pcm: bool = False,
) -> bytes:
    """Convert audio data to specified format using pydub.

    Handles both file formats (WAV, WebM, MP3, etc.) and raw PCM data.
    Uses pydub's automatic format detection and ffmpeg for conversions.

    Args:
        audio_data: Audio bytes (file format or raw PCM)
        output_format: Target format (default: "wav")
        sample_rate: Target sample rate in Hz (optional)
        channels: Target number of channels (optional)
        sample_width: Sample width in bytes for raw PCM (optional)
        is_raw_pcm: Whether input is raw PCM data (default: False)

    Returns:
        bytes: Converted audio data
    """
    # Load audio - pydub handles format detection automatically
    if is_raw_pcm:
        audio = AudioSegment(
            data=audio_data,
            sample_width=sample_width or 2,
            frame_rate=sample_rate or 24000,
            channels=channels or 1,
        )
    else:
        audio = AudioSegment.from_file(io.BytesIO(audio_data))

    # Apply transformations if specified
    if sample_rate:
        audio = audio.set_frame_rate(sample_rate)
    if channels:
        audio = audio.set_channels(channels)
    if sample_width:
        audio = audio.set_sample_width(sample_width)

    # Export to target format
    buffer = io.BytesIO()
    audio.export(buffer, format=output_format)
    return buffer.getvalue()
