"""
Azure Speech SDK Pronunciation Assessment Service.

This module handles communication with Azure Speech Service for pronunciation scoring.
It's called by AssessmentService (gemini_service.py) as step 2 in the pipeline.

Flow:
    [1] Receive audio bytes and reference text from AssessmentService
    [2] Configure Azure Speech SDK with pronunciation assessment settings
        - Grading system: HundredMark (0-100 scale)
        - Granularity: Phoneme (detailed word-level analysis)
        - Prosody assessment: Enabled for en-US only
        - Miscue detection: Configurable (detects omissions, insertions, mispronunciations)
    [3] Create push audio stream and recognizer
    [4] Push audio data and run recognition (async via thread pool)
    [5] Parse and return Azure response with scores and word-level data

Response Structure:
    - RecognitionStatus: "Success", "NoMatch", or error
    - NBest[0].PronunciationAssessment: Overall scores (PronScore, AccuracyScore, etc.)
    - NBest[0].Words[]: Word-level scores and phoneme details

Performance:
    - Async execution: Runs in thread pool (Speech SDK is synchronous)
    - Connection pooling: Handled internally by Speech SDK
    - Streaming: Push stream allows efficient audio transfer
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
    Send audio to Azure Speech SDK for pronunciation assessment (async).

    This function wraps the synchronous Azure Speech SDK in an async interface
    by running recognition in a thread pool executor.

    Flow:
        [1] Validate inputs (audio bytes and reference text)
        [2] Configure Speech SDK with subscription key and region
        [3] Build pronunciation assessment config:
            - Grading: HundredMark (0-100 scale)
            - Granularity: Phoneme (word and phoneme-level details)
            - Prosody: Enabled for en-US (rhythm/intonation scoring)
            - Miscue: Configurable (detects omissions, insertions, mispronunciations)
        [4] Create push audio stream and recognizer
        [5] Apply pronunciation config to recognizer
        [6] Run recognition in thread pool (SDK is synchronous):
            - Push audio bytes to stream
            - Close stream
            - Call recognize_once()
            - Parse JSON result
        [7] Handle recognition results:
            - Success: Return parsed JSON with scores and word data
            - NoMatch: Return empty result structure
            - Error: Raise AudioProcessingError

    Args:
        audio_bytes: Raw audio bytes (WAV/WebM format, SDK handles conversion)
        reference_text: Expected sentence for pronunciation comparison
        config: Application configuration (Speech key, region, language, settings)

    Returns:
        dict: Azure Speech API response containing:
            - RecognitionStatus: "Success", "NoMatch", or error
            - NBest[0].PronunciationAssessment: Overall scores (PronScore, AccuracyScore, FluencyScore, etc.)
            - NBest[0].Words[]: Word-level scores and phoneme details
            - NBest[0].Display: Recognized text

    Raises:
        AudioProcessingError: If audio/text is empty, or Azure SDK fails
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
        # Set speech recognition language
        speech_config.speech_recognition_language = config.speech_language_code
        speech_config.request_word_level_timestamps()

        # [2.3] Build pronunciation assessment config
        # Prosody disabled - focusing only on phoneme-level accuracy for young learners
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text.strip(),
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        )
        # Enable miscue detection to catch word substitutions (e.g., "bat" vs "mat")
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



