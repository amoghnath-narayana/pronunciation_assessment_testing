"""
Azure Speech SDK Pronunciation Assessment Service.

Handles Azure Speech Service communication for pronunciation scoring.
Called by AssessmentService to get raw pronunciation data from Azure.

Flow:
    [1] Configure Azure SDK with pronunciation settings (HundredMark, Phoneme granularity)
    [2] Create push stream and write audio bytes
    [3] Run recognition (async via thread pool, SDK is synchronous)
    [4] Return validated AzureRecognitionResult (Pydantic model)

Returns:
    AzureRecognitionResult with:
    - RecognitionStatus: Success/NoMatch/Error
    - pronunciation_scores: Overall scores (accuracy, fluency, completeness)
    - words: Word-level assessments with phoneme details
"""

import asyncio
import json

import azure.cognitiveservices.speech as speechsdk
import logfire

from config import AppConfig
from exceptions import AudioProcessingError
from models.assessment_models import AzureRecognitionResult


async def assess_pronunciation_async(
    audio_bytes: bytes,
    reference_text: str,
    config: AppConfig,
) -> AzureRecognitionResult:
    """
    Assess pronunciation using Azure Speech SDK.

    Wraps synchronous Azure SDK in async interface via thread pool.
    Validates audio/text, configures SDK, runs recognition, returns Pydantic model.

    Args:
        audio_bytes: Raw audio (WAV/WebM, SDK handles format detection)
        reference_text: Expected text for comparison
        config: Azure credentials and language settings

    Returns:
        AzureRecognitionResult: Validated model with:
            - is_successful: Quick status check
            - pronunciation_scores: Overall scores (accuracy, fluency, etc.)
            - words: Word-level assessments with phoneme details

    Raises:
        AudioProcessingError: Empty audio/text or Azure SDK failure
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
            """Inner function to run synchronous Azure SDK recognition."""
            # Write audio and close stream
            push_stream.write(audio_bytes)
            push_stream.close()

            # Run recognition
            sdk_recognition_result = recognizer.recognize_once()

            if sdk_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
                # Parse JSON response from Azure
                raw_json_response = json.loads(sdk_recognition_result.json)

                # Log pronunciation assessment metadata (optional additional info)
                try:
                    pron_assessment_obj = speechsdk.PronunciationAssessmentResult(sdk_recognition_result)
                    logfire.debug(
                        "Pronunciation assessment metadata",
                        accuracy=pron_assessment_obj.accuracy_score,
                        pronunciation=pron_assessment_obj.pronunciation_score
                    )
                except Exception as e:
                    logfire.debug("Pronunciation assessment object unavailable", error=str(e))

                return raw_json_response
            elif sdk_recognition_result.reason == speechsdk.ResultReason.NoMatch:
                logfire.warning("Azure: No speech recognized")
                return {"RecognitionStatus": "NoMatch", "DisplayText": "", "NBest": []}
            else:
                error_details = sdk_recognition_result.cancellation_details
                logfire.error(
                    "Azure recognition failed",
                    reason=error_details.reason,
                    error=error_details.error_details,
                )
                raise AudioProcessingError(
                    f"Azure recognition failed: {error_details.error_details}"
                )

        azure_response_dict = await loop.run_in_executor(None, _recognize)

        # Validate and convert to Pydantic model
        azure_response = AzureRecognitionResult(**azure_response_dict)

        # Log full response for debugging
        logfire.info(
            "Azure recognition complete",
            status=azure_response.RecognitionStatus,
            display_text=azure_response.DisplayText,
            is_successful=azure_response.is_successful,
        )

        # Print full JSON for debugging (avoid logfire formatting issues)
        print("\n" + "="*80)
        print("AZURE RESPONSE JSON:")
        print("="*80)
        print(json.dumps(azure_response_dict, indent=2))
        print("="*80 + "\n")

        # Log detailed scores if successful
        if azure_response.is_successful:
            scores = azure_response.pronunciation_scores
            words = azure_response.words

            word_summaries = [
                {
                    "word": w.Word,
                    "accuracy": w.PronunciationAssessment.AccuracyScore,
                    "error_type": w.PronunciationAssessment.ErrorType
                }
                for w in words
            ]

            logfire.info(
                "Azure pronunciation scores",
                pronunciation=scores.PronScore if scores else 0,
                accuracy=scores.AccuracyScore if scores else 0,
                fluency=scores.FluencyScore if scores else 0,
                completeness=scores.CompletenessScore if scores else 0,
                word_count=len(words),
                words=word_summaries
            )

            # Warn if scores are all zero (unexpected)
            if scores and all(s in (0, None) for s in [scores.PronScore, scores.AccuracyScore, scores.FluencyScore]):
                logfire.warn("Azure returned zero scores (unexpected)")
        else:
            logfire.warning(
                "Azure recognition unsuccessful",
                status=azure_response.RecognitionStatus
            )

        return azure_response

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



