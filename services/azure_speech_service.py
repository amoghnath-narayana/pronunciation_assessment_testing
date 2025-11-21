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
from typing import Any

import azure.cognitiveservices.speech as speechsdk
import logfire

from config import AppConfig
from exceptions import AudioProcessingError


async def assess_pronunciation_async(
    audio_bytes: bytes,
    reference_text: str,
    config: AppConfig,
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
        audio_bytes: Raw audio bytes (Azure SDK handles format conversion)
        reference_text: Expected sentence
        config: Application configuration

    Returns:
        dict: Azure response with RecognitionStatus, NBest[0].PronunciationAssessment, Words[]

    Raises:
        AudioProcessingError: If audio is empty or API fails
    """
    if not audio_bytes:
        raise AudioProcessingError("audio_bytes cannot be empty")
    if not reference_text or not reference_text.strip():
        raise AudioProcessingError("reference_text cannot be empty")

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
        speech_config.request_word_level_timestamps()

        # [2.3] Build pronunciation assessment config
        enable_prosody = config.speech_language_code.lower() == "en-us"
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text.strip(),
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        )

        # Enable prosody for en-US only
        if enable_prosody:
            pronunciation_config.enable_prosody_assessment()

        # Enable miscue detection
        if config.speech_enable_miscue:
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



