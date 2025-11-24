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
    logfire.info(
        "Step 2.1: Azure Speech SDK input validation",
        audio_bytes_present=bool(audio_bytes),
        audio_bytes_size=len(audio_bytes) if audio_bytes else 0,
        reference_text_present=bool(reference_text),
        reference_text=reference_text if reference_text else "EMPTY",
        speech_key_present=bool(config.speech_key),
        speech_region=config.speech_region,
        speech_language=config.speech_language_code,
    )

    if not audio_bytes:
        logfire.error("Audio bytes are empty or None")
        raise AudioProcessingError("audio_bytes cannot be empty")
    if not reference_text or not reference_text.strip():
        logfire.error("Reference text is empty or None", reference_text=reference_text)
        raise AudioProcessingError("reference_text cannot be empty")

    logfire.info(
        "Step 2.2: Azure Speech SDK call starting",
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

        # [2.3] Build pronunciation assessment config with NBestPhonemes support
        # Using JSON config to enable nBestPhonemeCount (not available via standard constructor)
        # This provides "what they actually said" vs "what was expected" for each phoneme
        pronunciation_config_json = {
            "referenceText": reference_text.strip(),
            "gradingSystem": "HundredMark",
            "granularity": "Phoneme",
            "phonemeAlphabet": "IPA",
            "nBestPhonemeCount": 5,  # Get top 5 alternative phonemes for each expected phoneme
        }
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            json_string=json.dumps(pronunciation_config_json)
        )
        pronunciation_config.enable_miscue = True
        pronunciation_config.enable_prosody_assessment = True
        
        # Create push stream for audio
        # Note: We write all audio at once (not chunked streaming). For short pre-recorded clips,
        # chunked streaming provides no latency benefit because the bottleneck is network upload
        # to Azure (~100-500ms) + Azure's pronunciation processing (~500-2000ms), not the local
        # stream writing time (~1-10ms). Chunked streaming only helps for real-time or long audio.
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
                json_result = json.loads(result.json)
                
                # Try to get pronunciation assessment result object for NBestPhonemes
                # This is separate from the JSON and may contain additional data
                try:
                    pron_result = speechsdk.PronunciationAssessmentResult(result)
                    logfire.debug("PronunciationAssessmentResult object created", 
                                 accuracy=pron_result.accuracy_score,
                                 pronunciation=pron_result.pronunciation_score)
                except Exception as e:
                    logfire.debug("Could not create PronunciationAssessmentResult", error=str(e))
                
                return json_result
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
        
        # Always log the full Azure response for debugging
        nbest_list = result.get("NBest", [])
        nbest_displays = [nb.get("Display", "") for nb in nbest_list] if nbest_list else []

        # Log full response as JSON string for visibility
        logfire.info(
            "Azure full response",
            recognition_status=status,
            display_text=result.get("DisplayText", ""),
            nbest_count=len(nbest_list),
            nbest_displays=nbest_displays,
        )

        # Use print to avoid logfire format issues with JSON
        print("\n" + "="*80)
        print("AZURE RESPONSE JSON:")
        print("="*80)
        print(json.dumps(result, indent=2))
        print("="*80 + "\n")
        
        if status == "Success" and result.get("NBest"):
            scores = result["NBest"][0].get("PronunciationAssessment", {})
            words = result["NBest"][0].get("Words", [])
            
            # Log word-by-word details
            word_details = []
            for w in words:
                word_details.append({
                    "word": w.get("Word"),
                    "accuracy": w.get("PronunciationAssessment", {}).get("AccuracyScore"),
                    "error_type": w.get("PronunciationAssessment", {}).get("ErrorType")
                })
            
            logfire.info(
                "Step 2.5: Azure SDK complete",
                pron=scores.get("PronScore"),
                acc=scores.get("AccuracyScore"),
                flu=scores.get("FluencyScore"),
                word_count=len(words),
                words=word_details
            )
            
            if not scores or all(v in (0, None) for v in scores.values()):
                logfire.warn(
                    "Azure returned zero/empty scores",
                    raw_result_preview=str(result)[:500],
                )
        else:
            logfire.warning("Azure non-success", status=status, full_result=result)

        return result

    except Exception as e:
        logfire.error(
            "Azure SDK error - FULL DETAILS",
            error=str(e),
            error_type=type(e).__name__,
            audio_size=len(audio_bytes) if audio_bytes else 0,
            reference_text=reference_text,
            speech_language=config.speech_language_code,
            speech_region=config.speech_region,
            traceback=str(e.__traceback__),
        )
        # Log full exception with traceback
        import traceback
        logfire.error("Full exception traceback:\n" + traceback.format_exc())
        raise AudioProcessingError(f"Azure SDK failed: {e}") from e



