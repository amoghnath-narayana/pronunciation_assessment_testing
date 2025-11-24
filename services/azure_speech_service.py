"""
Azure Speech SDK Pronunciation Assessment Service.

Handles Azure Speech Service communication for pronunciation scoring using continuous recognition.
Returns validated AzureRecognitionResult (Pydantic model) with word/phoneme-level details.
"""

import asyncio
import json
import string
import difflib
import time
from typing import Any

import azure.cognitiveservices.speech as speechsdk
import logfire

from config import AppConfig
from exceptions import AudioProcessingError
from models.assessment_models import AzureRecognitionResult, AzureNBestResult


async def assess_pronunciation_async(
    audio_bytes: bytes,
    reference_text: str,
    config: AppConfig,
) -> AzureRecognitionResult:
    """
    Assess pronunciation using Azure Speech SDK continuous recognition.

    Args:
        audio_bytes: Raw audio (WAV/WebM)
        reference_text: Expected text for comparison
        config: Azure credentials and language settings

    Returns:
        AzureRecognitionResult with pronunciation scores and word-level details

    Raises:
        AudioProcessingError: Empty audio/text or Azure SDK failure
    """
    # Validate inputs
    if not audio_bytes:
        raise AudioProcessingError("audio_bytes cannot be empty")
    if not reference_text or not reference_text.strip():
        raise AudioProcessingError("reference_text cannot be empty")

    logfire.info(
        "Azure assessment starting",
        audio_size=len(audio_bytes),
        text_preview=reference_text[:50],
        language=config.speech_language_code,
    )

    try:
        # Configure Azure SDK
        speech_config = speechsdk.SpeechConfig(
            subscription=config.speech_key, region=config.speech_region
        )
        speech_config.speech_recognition_language = config.speech_language_code
        speech_config.request_word_level_timestamps()

        # Pronunciation config with phoneme-level details
        pron_config = speechsdk.PronunciationAssessmentConfig(
            json_string=json.dumps({
                "referenceText": reference_text.strip(),
                "gradingSystem": "HundredMark",
                "granularity": "Phoneme",
                "phonemeAlphabet": "IPA",
                "nBestPhonemeCount": 5,
            })
        )
        pron_config.enable_miscue = True
        pron_config.enable_prosody_assessment = True

        # Setup recognizer
        push_stream = speechsdk.audio.PushAudioInputStream()
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config
        )
        pron_config.apply_to(recognizer)

        # Run recognition in thread pool (SDK is synchronous)
        loop = asyncio.get_event_loop()

        def _recognize() -> dict[str, Any]:
            """Run synchronous Azure SDK continuous recognition."""
            push_stream.write(audio_bytes)
            push_stream.close()

            # State tracking
            state = {
                "done": False,
                "error": None,
                "words": [],
                "fluency_scores": [],
                "prosody_scores": [],
                "durations": [],
                "texts": [],
                "raw_json": [],
            }

            def on_recognized(evt: speechsdk.SpeechRecognitionEventArgs):
                """Handle recognized speech events."""
                result = speechsdk.PronunciationAssessmentResult(evt.result)
                state["texts"].append(evt.result.text)
                state["words"].extend(result.words)
                
                if result.fluency_score is not None:
                    state["fluency_scores"].append(result.fluency_score)
                if result.prosody_score is not None:
                    state["prosody_scores"].append(result.prosody_score)

                # Store raw JSON for phoneme data
                json_str = evt.result.properties.get(
                    speechsdk.PropertyId.SpeechServiceResponse_JsonResult
                )
                jo = json.loads(json_str)
                state["raw_json"].append(jo)

                if "NBest" in jo and jo["NBest"]:
                    words = jo["NBest"][0].get("Words", [])
                    duration = sum(int(w.get("Duration", 0)) for w in words)
                    state["durations"].append(duration)

            def on_canceled(evt: speechsdk.SpeechRecognitionCanceledEventArgs):
                """Handle cancellation."""
                if evt.reason == speechsdk.CancellationReason.Error:
                    state["error"] = evt.error_details
                state["done"] = True

            def on_stopped(evt: speechsdk.SessionEventArgs):
                """Handle session stop."""
                state["done"] = True

            # Connect callbacks
            recognizer.recognized.connect(on_recognized)
            recognizer.canceled.connect(on_canceled)
            recognizer.session_stopped.connect(on_stopped)

            # Run recognition
            recognizer.start_continuous_recognition()
            
            timeout = 30
            elapsed = 0
            while not state["done"] and elapsed < timeout:
                time.sleep(0.5)
                elapsed += 0.5

            recognizer.stop_continuous_recognition()

            if state["error"]:
                raise AudioProcessingError(f"Azure recognition failed: {state['error']}")

            if not state["words"]:
                return {"RecognitionStatus": "NoMatch", "DisplayText": "", "NBest": []}

            # Calculate scores from collected data
            reference_words = [
                w.strip(string.punctuation) for w in reference_text.lower().split()
            ]
            
            # Apply miscue detection using difflib
            final_words = _apply_miscue_detection(
                reference_words, state["words"], pron_config.enable_miscue
            )

            # Calculate final scores
            accuracy = _calculate_accuracy(final_words)
            fluency = _calculate_fluency(state["fluency_scores"], state["durations"])
            completeness = _calculate_completeness(state["words"], reference_words)
            prosody = _calculate_prosody(state["prosody_scores"])
            
            # Overall pronunciation score (weighted)
            if prosody > 0:
                pron_score = (
                    accuracy * 0.4 + prosody * 0.2 + fluency * 0.2 + completeness * 0.2
                )
            else:
                pron_score = accuracy * 0.5 + fluency * 0.25 + completeness * 0.25

            logfire.info(
                "Scores calculated",
                pronunciation=pron_score,
                accuracy=accuracy,
                fluency=fluency,
                completeness=completeness,
                prosody=prosody,
            )

            # Build response with phoneme data
            display_text = " ".join(state["texts"])
            word_phoneme_map = _build_phoneme_map(state["raw_json"])
            words_json = _build_words_json(final_words, word_phoneme_map)

            return {
                "RecognitionStatus": "Success",
                "DisplayText": display_text,
                "NBest": [
                    {
                        "Confidence": 0.9,
                        "Lexical": display_text.lower(),
                        "ITN": display_text,
                        "MaskedITN": display_text,
                        "Display": display_text,
                        "PronunciationAssessment": {
                            "AccuracyScore": accuracy,
                            "FluencyScore": fluency,
                            "CompletenessScore": completeness,
                            "PronScore": pron_score,
                            "ProsodyScore": prosody,
                        },
                        "Words": words_json,
                    }
                ],
            }

        result_dict = await loop.run_in_executor(None, _recognize)
        result = AzureRecognitionResult(**result_dict)

        logfire.info(
            "Azure assessment complete",
            status=result.RecognitionStatus,
            success=result.is_successful,
            word_count=len(result.words),
        )

        return result

    except Exception as e:
        logfire.error("Azure SDK error", error=str(e), error_type=type(e).__name__)
        raise AudioProcessingError(f"Azure SDK failed: {e}") from e



# ============================================================================
# Helper Functions
# ============================================================================


def _apply_miscue_detection(
    reference_words: list[str], recognized_words: list, enable_miscue: bool
) -> list[dict[str, Any]]:
    """Apply miscue detection using difflib to match recognized vs reference words."""
    if not enable_miscue:
        return [
            {
                "word": w.word,
                "accuracy_score": w.accuracy_score,
                "error_type": w.error_type,
            }
            for w in recognized_words
        ]

    final_words = []
    diff = difflib.SequenceMatcher(
        None, reference_words, [w.word.lower() for w in recognized_words]
    )

    for tag, i1, i2, j1, j2 in diff.get_opcodes():
        if tag in ["insert", "replace"]:
            for word in recognized_words[j1:j2]:
                error_type = "Insertion" if word.error_type == "None" else word.error_type
                final_words.append({
                    "word": word.word,
                    "accuracy_score": word.accuracy_score,
                    "error_type": error_type,
                })

        if tag in ["delete", "replace"]:
            for word_text in reference_words[i1:i2]:
                final_words.append({
                    "word": word_text,
                    "accuracy_score": 0,
                    "error_type": "Omission",
                })

        if tag == "equal":
            for word in recognized_words[j1:j2]:
                final_words.append({
                    "word": word.word,
                    "accuracy_score": word.accuracy_score,
                    "error_type": word.error_type,
                })

    return final_words


def _calculate_accuracy(final_words: list[dict[str, Any]]) -> float:
    """Calculate accuracy score (average of non-insertion words)."""
    scores = [
        w["accuracy_score"]
        for w in final_words
        if w["error_type"] != "Insertion" and w["accuracy_score"] is not None
    ]
    return sum(scores) / len(scores) if scores else 0.0


def _calculate_fluency(fluency_scores: list[float], durations: list[int]) -> float:
    """Calculate fluency score (duration-weighted average)."""
    if not fluency_scores:
        return 0.0

    if durations and len(durations) == len(fluency_scores):
        valid_pairs = [
            (f, d) for f, d in zip(fluency_scores, durations) if f is not None and d
        ]
        if valid_pairs:
            return sum(f * d for f, d in valid_pairs) / sum(d for _, d in valid_pairs)

    valid_scores = [f for f in fluency_scores if f is not None]
    return sum(valid_scores) / len(valid_scores) if valid_scores else 0.0


def _calculate_completeness(recognized_words: list, reference_words: list[str]) -> float:
    """Calculate completeness score (percentage of reference words spoken correctly)."""
    if not reference_words:
        return 0.0
    correct = len([w for w in recognized_words if w.error_type == "None"])
    return min((correct / len(reference_words)) * 100, 100.0)


def _calculate_prosody(prosody_scores: list[float]) -> float:
    """Calculate prosody score (simple average)."""
    valid_scores = [p for p in prosody_scores if p is not None]
    return sum(valid_scores) / len(valid_scores) if valid_scores else 0.0


def _build_phoneme_map(raw_json_responses: list[dict[str, Any]]) -> dict[str, dict]:
    """Build map of words to their phoneme data from raw JSON responses."""
    phoneme_map = {}
    for json_resp in raw_json_responses:
        if "NBest" in json_resp and json_resp["NBest"]:
            words = json_resp["NBest"][0].get("Words", [])
            for w in words:
                word_text = w.get("Word", "").lower()
                phoneme_map[word_text] = w
    return phoneme_map


def _build_words_json(
    final_words: list[dict[str, Any]], phoneme_map: dict[str, dict]
) -> list[dict[str, Any]]:
    """Build words JSON with phoneme data preserved."""
    words_json = []
    for word in final_words:
        word_dict = {
            "Word": word["word"],
            "Offset": 0,
            "Duration": 0,
            "PronunciationAssessment": {
                "AccuracyScore": word["accuracy_score"],
                "ErrorType": word["error_type"],
            },
        }

        # Add phoneme/syllable data if available
        raw_data = phoneme_map.get(word["word"].lower())
        if raw_data:
            if "Phonemes" in raw_data:
                word_dict["Phonemes"] = raw_data["Phonemes"]
            if "Syllables" in raw_data:
                word_dict["Syllables"] = raw_data["Syllables"]

        words_json.append(word_dict)

    return words_json
