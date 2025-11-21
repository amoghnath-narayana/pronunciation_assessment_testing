"""
TTS Narration Composer - Builds final audio feedback from static and dynamic segments.

This service composes the final TTS audio by combining:
    - Static clips: Pre-recorded intros/outros from TTSAssetLoader
    - Dynamic segments: Error-specific TTS from TTSCacheService (Gemini TTS API)

Composition Logic:
    - Perfect reading (no errors):
        → Single "perfect_intro" clip
    
    - Has errors:
        → "needs_work_intro" clip
        → Dynamic TTS for each error (word + issue + suggestion)
        → "closing_cheer" clip

Audio Processing:
    - Concatenation: pydub's sum() for seamless joining
    - Normalization: Loudness normalization to prevent volume jumps
    - Export: Final audio exported as WAV bytes

Used by: AssessmentService.generate_tts_narration_async()
"""

import io
from dataclasses import dataclass

import logfire
from pydub import AudioSegment

from models.assessment_models import AzureAnalysisResult
from services.tts_assets import TTSAssetLoader
from services.tts_cache import TTSCacheService


@dataclass
class TTSNarrationComposer:
    """Composes final TTS audio from static and dynamic segments."""

    asset_loader: TTSAssetLoader
    cache_service: TTSCacheService

    def compose(self, assessment_result: AzureAnalysisResult) -> bytes:
        """
        Compose final TTS audio from assessment result.

        This method builds the complete audio narration by combining static clips
        with dynamically generated TTS for specific error corrections.

        Flow:
            [1] Check if perfect reading (no word_level_feedback):
                → Return single "perfect_intro" clip
            
            [2] If has errors, build multi-segment audio:
                → Add "needs_work_intro" clip
                → For each error in word_level_feedback:
                    - Build error text: "{issue} {suggestion}"
                    - Get cached or generate TTS via cache_service
                    - Convert bytes to AudioSegment
                    - Append to segments
                → Add "closing_cheer" clip
            
            [3] Concatenate all segments (pydub's sum())
            [4] Normalize loudness to prevent volume jumps
            [5] Export as WAV bytes

        Args:
            assessment_result: Assessment result containing word_level_feedback (specific_errors)

        Returns:
            bytes: Final composed audio as WAV bytes

        Raises:
            ValueError: If required assets (intro/outro) are missing
            Exception: If TTS generation or audio processing fails
        """
        try:
            # Handle perfect reading case (no errors)
            if not assessment_result.specific_errors:
                logfire.info("Composing perfect reading narration (single intro clip)")
                intro = self.asset_loader.pick("perfect_intro")
                normalized = self._normalize_loudness(intro)
                return self._export_wav(normalized)

            # Handle error case (intro + dynamic errors + outro)
            logfire.info(
                f"Composing error narration with {len(assessment_result.specific_errors)} errors"
            )
            segments = []

            # Add intro clip
            try:
                intro = self.asset_loader.pick("needs_work_intro")
                segments.append(intro)
                logfire.debug("Added needs_work_intro clip")
            except ValueError as e:
                logfire.error(f"Failed to load intro clip: {e}")
                raise ValueError("Missing required asset: needs_work_intro") from e

            # Add dynamic error corrections (SIMPLIFIED for speed)
            # Only process first error for demo speed
            for idx, error in enumerate(assessment_result.specific_errors[:1]):  # Limit to 1 error
                try:
                    # Build MINIMAL error text for TTS (max 7-8 words for speed)
                    # Format: "Word '<word>': say '<expected>' not '<actual>'"
                    error_text = f"Word {error.word}, say {error.expected_sound} not {error.actual_sound}"

                    logfire.info(f"Generating TTS for: {error_text}")
                    
                    # Get cached or generate TTS audio
                    error_audio_bytes = self.cache_service.get_or_generate(error_text)
                    
                    if error_audio_bytes:
                        # Convert bytes to AudioSegment
                        error_segment = AudioSegment.from_wav(io.BytesIO(error_audio_bytes))
                        segments.append(error_segment)
                        logfire.debug(f"Added dynamic error clip for '{error.word}'")
                    else:
                        logfire.warning(f"No TTS audio generated for '{error.word}'")

                except Exception as e:
                    logfire.error(
                        f"Failed to generate error clip for '{error.word}': {e}"
                    )
                    # Continue with other errors rather than failing completely
                    continue

            # Add outro clip
            try:
                outro = self.asset_loader.pick("closing_cheer")
                segments.append(outro)
                logfire.debug("Added closing_cheer clip")
            except ValueError as e:
                logfire.error(f"Failed to load outro clip: {e}")
                raise ValueError("Missing required asset: closing_cheer") from e

            # Ensure we have at least some segments
            if not segments:
                raise ValueError("No audio segments available for composition")

            # Concatenate all segments
            if len(segments) == 1:
                final_audio = segments[0]
            else:
                final_audio = sum(segments)

            # Normalize loudness to prevent volume jumps
            normalized = self._normalize_loudness(final_audio)

            # Calculate total duration for logging
            duration_seconds = len(normalized) / 1000.0
            logfire.info(
                f"Composed audio: {len(segments)} segments, {duration_seconds:.2f}s total"
            )

            return self._export_wav(normalized)

        except Exception as e:
            logfire.error(f"Audio composition failed: {e}")
            raise

    def _normalize_loudness(self, audio: AudioSegment) -> AudioSegment:
        """Apply loudness normalization using pydub's built-in method.

        Args:
            audio: The audio segment to normalize

        Returns:
            AudioSegment: Normalized audio segment
        """
        try:
            # Use pydub's normalize() with headroom to prevent clipping
            normalized = audio.normalize(headroom=0.1)
            logfire.debug("Normalized audio loudness")
            return normalized
        except Exception as e:
            logfire.warning(
                f"Loudness normalization failed: {e}, returning original audio"
            )
            return audio

    def _export_wav(self, audio: AudioSegment) -> bytes:
        """Export AudioSegment to WAV bytes.

        Args:
            audio: The audio segment to export

        Returns:
            bytes: WAV format audio data
        """
        try:
            buffer = io.BytesIO()
            audio.export(buffer, format="wav")
            wav_bytes = buffer.getvalue()
            logfire.debug(f"Exported audio to WAV: {len(wav_bytes)} bytes")
            return wav_bytes
        except Exception as e:
            logfire.error(f"Failed to export audio to WAV: {e}")
            raise
