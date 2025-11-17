"""Utility functions for the Pronunciation Assessment Application."""

from __future__ import annotations

import io
import wave

import streamlit as st


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Convert raw PCM audio data to WAV format.
    
    Args:
        pcm_data: Raw PCM audio bytes
        sample_rate: Audio sample rate in Hz (default: 24000)
        channels: Number of audio channels (default: 1 for mono)
        sample_width: Sample width in bytes (default: 2 for 16-bit)
        
    Returns:
        bytes: WAV format audio data
    """
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return wav_buffer.getvalue()


def create_practice_sentence_display_box(sentence_text: str) -> None:
    """
    Create a styled display box for the practice sentence.

    Args:
        sentence_text: The sentence to display
    """
    st.markdown(
        f"""
        <div style="
            border-radius: 24px;
            border: dashed 3px grey;
            padding: 24px;
            margin: 16px 0;
        ">
            <h3 style="text-align: center; color: #1f1f1f; font-size: 1.3em; line-height: 1.6; margin: 0;">
                {sentence_text}
            </h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
