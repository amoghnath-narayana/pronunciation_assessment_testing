"""Utility functions for the Pronunciation Assessment Application."""

from __future__ import annotations

import io
import os
import tempfile
from contextlib import contextmanager
from typing import Generator

from pydub import AudioSegment


@contextmanager
def temp_audio_file(audio_data: bytes, suffix: str = ".wav") -> Generator[str, None, None]:
    """Context manager for temporary audio files with guaranteed cleanup.
    
    Creates a temporary file, writes audio data to it, yields the path,
    and ensures the file is deleted even if an exception occurs.
    
    Args:
        audio_data: Audio data bytes to write to the temporary file
        suffix: File extension/suffix (default: ".wav")
        
    Yields:
        str: Path to the temporary file
        
    Example:
        with temp_audio_file(audio_bytes, ".mp3") as temp_path:
            # Use temp_path for operations
            result = process_file(temp_path)
        # File is automatically deleted here
    """
    temp_path = None
    try:
        # Create temporary file and write data
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(audio_data)
            temp_path = f.name
        
        # Yield the path for use in the with block
        yield temp_path
        
    finally:
        # Guaranteed cleanup: delete the file if it exists
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                # Log but don't raise - cleanup is best effort
                pass


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Convert raw PCM audio data to WAV format using pydub.
    
    Args:
        pcm_data: Raw PCM audio bytes
        sample_rate: Audio sample rate in Hz (default: 24000)
        channels: Number of audio channels (default: 1 for mono)
        sample_width: Sample width in bytes (default: 2 for 16-bit)
        
    Returns:
        bytes: WAV format audio data
    """
    # Create AudioSegment from raw PCM data
    audio = AudioSegment(
        data=pcm_data,
        sample_width=sample_width,
        frame_rate=sample_rate,
        channels=channels
    )
    
    # Export to WAV format
    buffer = io.BytesIO()
    audio.export(buffer, format="wav")
    return buffer.getvalue()
