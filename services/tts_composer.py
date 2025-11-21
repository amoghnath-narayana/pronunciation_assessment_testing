"""Service for composing final TTS audio from static and dynamic segments."""

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
        """Build final audio from assessment result.

        Args:
            assessment_result: The assessment result containing error information

        Returns:
            bytes: Final composed audio as WAV bytes

        Raises:
            ValueError: If assets are not available or composition fails
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

            # Add dynamic error corrections
            for idx, error in enumerate(assessment_result.specific_errors):
                try:
                    # Build error text for TTS
                    error_text = f"{error.issue} {error.suggestion}"

                    # Get cached or generate TTS audio
                    error_audio_bytes = self.cache_service.get_or_generate(error_text)

                    # Convert bytes to AudioSegment
                    error_segment = AudioSegment.from_wav(io.BytesIO(error_audio_bytes))
                    segments.append(error_segment)
                    logfire.debug(
                        f"Added dynamic error clip {idx + 1}/{len(assessment_result.specific_errors)}"
                    )

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
        """Apply loudness normalization to prevent volume jumps.

        Uses match_target_amplitude to normalize to -20 dBFS, which is
        a standard level for speech audio (not too loud, not too quiet).

        Args:
            audio: The audio segment to normalize

        Returns:
            AudioSegment: Normalized audio segment
        """
        try:
            # Target -20 dBFS for speech (standard level)
            target_dbfs = -20.0
            normalized = audio.apply_gain(target_dbfs - audio.dBFS)
            logfire.debug(
                f"Normalized audio from {audio.dBFS:.2f} dBFS to {normalized.dBFS:.2f} dBFS"
            )
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
