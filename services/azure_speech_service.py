"""
Azure Speech Pronunciation Assessment Service.

Step 2 in the pipeline: Sends audio to Azure and receives pronunciation scores.

Flow:
    [2.1] Receive audio bytes and reference text from AssessmentService
    [2.2] Build pronunciation assessment config (HundredMark, Phoneme, Comprehensive)
    [2.3] Configure Speech SDK recognizer with pronunciation assessment
    [2.4] Push audio stream and recognize (async)
    [2.5] Return parsed Azure response with scores and word-level analysis

Optimization:
    - Speech SDK handles connection pooling and streaming internally
    - Async recognition for non-blocking I/O
    - Prosody assessment enabled for en-US
"""

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

import azure.cognitiveservices.speech as speechsdk
import logfire

from exceptions import ConfigurationError, AudioProcessingError
from utils import ensure_wav_pcm16


@dataclass
class AzureSpeechConfig:
    """Configuration for Azure Speech service."""

    speech_key: str
    speech_region: str
    language_code: str = "en-US"
    enable_miscue: bool = True

    @classmethod
    def from_env(cls) -> "AzureSpeechConfig":
        """
        Load configuration from environment variables.

        Returns:
            AzureSpeechConfig: Configuration instance

        Raises:
            ConfigurationError: If required environment variables are missing
        """
        speech_key = os.environ.get("SPEECH_KEY")
        speech_region = os.environ.get("SPEECH_REGION")

        if not speech_key:
            raise ConfigurationError("SPEECH_KEY environment variable is not set")
        if not speech_region:
            raise ConfigurationError("SPEECH_REGION environment variable is not set")

        return cls(speech_key=speech_key, speech_region=speech_region)


async def assess_pronunciation_async(
    audio_bytes: bytes,
    reference_text: str,
    language_code: str = "en-IN",
    config: AzureSpeechConfig | None = None,
) -> dict[str, Any]:
    """
    Step 2: Send audio to Azure Speech for pronunciation assessment using SDK.

    Flow:
        [2.1] Validate inputs
        [2.2] Build pronunciation assessment config (HundredMark, Phoneme, Comprehensive)
        [2.3] Configure Speech SDK recognizer with pronunciation assessment
        [2.4] Push audio stream and recognize (async)
        [2.5] Return assessment results

    Args:
        audio_bytes: Raw audio bytes (WAV/WebM)
        reference_text: Expected sentence
        language_code: Language code (default: "en-IN")
        config: Azure config (loads from env if None)

    Returns:
        dict: Azure response with RecognitionStatus, NBest[0].PronunciationAssessment, Words[]

    Raises:
        AudioProcessingError: If audio is empty or API fails
    """
    if not audio_bytes:
        raise AudioProcessingError("audio_bytes cannot be empty")
    if not reference_text or not reference_text.strip():
        raise AudioProcessingError("reference_text cannot be empty")
    if config is None:
        config = AzureSpeechConfig.from_env()

    # Normalize audio to 16 kHz PCM WAV to match Azure SDK requirements
    try:
        audio_bytes = ensure_wav_pcm16(audio_bytes)
    except Exception as e:
        logfire.error("Audio normalization failed", error=str(e))
        raise AudioProcessingError(
            "Audio must be convertible to 16kHz mono PCM WAV for Azure Pronunciation Assessment"
        ) from e

    logfire.info(
        "Step 2.2: Azure Speech SDK call",
        audio_bytes=len(audio_bytes),
        text=reference_text[:50],
    )

    # [2.2] Configure Speech SDK
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=config.speech_key, region=config.speech_region
        )
        speech_config.speech_recognition_language = language_code
        speech_config.request_word_level_timestamps()
        speech_config.output_format = speechsdk.OutputFormat.Detailed

        # [2.3] Build pronunciation assessment config
        enable_prosody = language_code.lower() == "en-us"
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text.strip(),
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        )

        # Enable prosody for en-US only
        if enable_prosody:
            pronunciation_config.enable_prosody_assessment()

        # Enable miscue detection
        if config.enable_miscue:
            pronunciation_config.enable_miscue = True

        # Create push stream for audio
        push_stream = speechsdk.audio.PushAudioInputStream()
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

        # Create recognizer
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config
        )

        # Apply pronunciation assessment config
        pronunciation_config.apply_to(recognizer)

        # [2.4] Run recognition in thread pool (SDK is sync)
        loop = asyncio.get_event_loop()

        def _recognize():
            # Push audio data
            push_stream.write(audio_bytes)
            push_stream.close()

            # Recognize once
            result = recognizer.recognize_once()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                # Parse JSON result
                return json.loads(result.json)
            elif result.reason == speechsdk.ResultReason.NoMatch:
                logfire.warning("Azure: No speech recognized")
                return {"RecognitionStatus": "NoMatch", "DisplayText": "", "NBest": []}
            else:
                error_details = result.cancellation_details
                logfire.error(
                    "Azure recognition failed",
                    reason=error_details.reason,
                    error=error_details.error_details,
                )
                raise AudioProcessingError(
                    f"Azure recognition failed: {error_details.error_details}"
                )

        result = await loop.run_in_executor(None, _recognize)

        # [2.5] Log results
        status = result.get("RecognitionStatus", "Unknown")
        if status == "Success" and result.get("NBest"):
            scores = result["NBest"][0].get("PronunciationAssessment", {})
            logfire.info(
                "Step 2.5: Azure SDK complete",
                pron=scores.get("PronScore"),
                acc=scores.get("AccuracyScore"),
                flu=scores.get("FluencyScore"),
            )
            if not scores or all(v in (0, None) for v in scores.values()):
                logfire.warn(
                    "Azure returned zero/empty scores",
                    raw_result_preview=str(result)[:500],
                )
                logfire.debug("Azure full result", raw_result=result)
        else:
            logfire.warning("Azure non-success", status=status)

        return result

    except Exception as e:
        logfire.error("Azure SDK error", error=str(e))
        raise AudioProcessingError(f"Azure SDK failed: {e}") from e


def extract_assessment_summary(azure_result: dict[str, Any]) -> dict[str, Any]:
    """Extract a summary of key scores from Azure assessment result.

    Convenience function to pull out the most important scores and word-level
    details from the full Azure response.

    Args:
        azure_result: Full response from assess_pronunciation_with_azure()

    Returns:
        dict: Summarized assessment containing:
            - recognition_status: Overall status
            - overall_scores: Dict with PronScore, AccuracyScore, etc.
            - words: List of word assessments with scores
            - prosody_feedback: Prosody-specific feedback if available
            - display_text: What Azure recognized the user said
    """
    if not azure_result:
        return {"recognition_status": "NoResult", "overall_scores": {}, "words": []}

    recognition_status = azure_result.get("RecognitionStatus", "Unknown")

    if recognition_status != "Success" or not azure_result.get("NBest"):
        return {
            "recognition_status": recognition_status,
            "overall_scores": {},
            "words": [],
            "display_text": "",
        }

    nbest = azure_result["NBest"][0]
    assessment = nbest.get("PronunciationAssessment", {})

    # Extract overall scores
    overall_scores = {
        "pronunciation_score": assessment.get("PronScore", 0),
        "accuracy_score": assessment.get("AccuracyScore", 0),
        "fluency_score": assessment.get("FluencyScore", 0),
        "completeness_score": assessment.get("CompletenessScore", 0),
        "prosody_score": assessment.get("ProsodyScore", 0),
    }

    # Extract word-level details
    words = []
    for word_data in nbest.get("Words", []):
        word_assessment = word_data.get("PronunciationAssessment", {})
        word_info = {
            "word": word_data.get("Word", ""),
            "accuracy_score": word_assessment.get("AccuracyScore", 0),
            "error_type": word_assessment.get("ErrorType", "None"),
        }

        # Include phoneme details if available
        if "Phonemes" in word_data:
            word_info["phonemes"] = [
                {
                    "phoneme": p.get("Phoneme", ""),
                    "accuracy_score": p.get("PronunciationAssessment", {}).get(
                        "AccuracyScore", 0
                    ),
                }
                for p in word_data["Phonemes"]
            ]

        words.append(word_info)

    # Extract prosody feedback if available
    prosody_feedback = assessment.get("Feedback", {}).get("Prosody", {})

    return {
        "recognition_status": recognition_status,
        "overall_scores": overall_scores,
        "words": words,
        "prosody_feedback": prosody_feedback,
        "display_text": nbest.get("Display", ""),
    }
