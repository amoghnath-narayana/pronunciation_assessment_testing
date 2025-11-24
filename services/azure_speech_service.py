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
import string
import difflib
import io

import azure.cognitiveservices.speech as speechsdk
import logfire
from pydub import AudioSegment

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
            """Inner function to run synchronous Azure SDK continuous recognition."""
            # Write audio and close stream
            push_stream.write(audio_bytes)
            push_stream.close()

            # State variables for continuous recognition
            done = False
            recognized_words = []
            fluency_scores = []
            prosody_scores = []
            durations = []
            all_recognized_texts = []
            recognition_error = None

            def stop_cb(evt: speechsdk.SessionEventArgs):
                """Callback to stop continuous recognition."""
                nonlocal done
                logfire.debug("Session stopped", event=str(evt))
                done = True

            def canceled_cb(evt: speechsdk.SpeechRecognitionCanceledEventArgs):
                """Callback for cancellation events."""
                nonlocal done, recognition_error
                logfire.warning("Recognition canceled", reason=evt.reason)
                if evt.reason == speechsdk.CancellationReason.Error:
                    recognition_error = evt.error_details
                    logfire.error("Recognition error", error=evt.error_details)
                done = True

            def recognizing(evt: speechsdk.SpeechRecognitionEventArgs):
                """Callback for intermediate recognition results."""
                logfire.debug("RECOGNIZING", text=evt.result.text)
                print(f"RECOGNIZING: {evt.result.text}")

            # Store raw JSON responses to preserve phoneme data
            raw_json_responses = []
            
            def recognized(evt: speechsdk.SpeechRecognitionEventArgs):
                """Callback for recognized speech events."""
                nonlocal recognized_words, fluency_scores, prosody_scores, durations, all_recognized_texts, raw_json_responses

                print(f"RECOGNIZED: {evt.result.text}")
                logfire.info("Recognition event", text=evt.result.text)
                all_recognized_texts.append(evt.result.text)

                # Get pronunciation assessment result
                pronunciation_result = speechsdk.PronunciationAssessmentResult(evt.result)

                print(f"    Accuracy: {pronunciation_result.accuracy_score}, "
                      f"Pronunciation: {pronunciation_result.pronunciation_score}, "
                      f"Completeness: {pronunciation_result.completeness_score}, "
                      f"Fluency: {pronunciation_result.fluency_score}, "
                      f"Prosody: {pronunciation_result.prosody_score}")

                logfire.info(
                    "Pronunciation scores for segment",
                    accuracy=pronunciation_result.accuracy_score,
                    pronunciation=pronunciation_result.pronunciation_score,
                    completeness=pronunciation_result.completeness_score,
                    fluency=pronunciation_result.fluency_score,
                    prosody=pronunciation_result.prosody_score
                )

                # Collect words with their scores (handle None values)
                recognized_words.extend(pronunciation_result.words)
                if pronunciation_result.fluency_score is not None:
                    fluency_scores.append(pronunciation_result.fluency_score)
                if pronunciation_result.prosody_score is not None:
                    prosody_scores.append(pronunciation_result.prosody_score)

                # Extract duration and raw JSON response (with phoneme data)
                json_result = evt.result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
                jo = json.loads(json_result)
                
                # Store raw JSON to preserve phoneme data
                raw_json_responses.append(jo)
                
                # Print full JSON for debugging
                print("Full JSON Response:")
                print(json.dumps(jo, indent=2))
                
                if 'NBest' in jo and len(jo['NBest']) > 0:
                    nb = jo['NBest'][0]
                    if 'Words' in nb:
                        segment_duration = sum([int(w.get('Duration', 0)) for w in nb['Words']])
                        durations.append(segment_duration)

            # Connect callbacks (matching Azure sample pattern)
            recognizer.recognizing.connect(recognizing)
            recognizer.recognized.connect(recognized)
            recognizer.session_started.connect(lambda evt: print(f"SESSION STARTED: {evt}"))
            recognizer.session_stopped.connect(lambda evt: print(f"SESSION STOPPED: {evt}"))
            recognizer.session_stopped.connect(stop_cb)
            recognizer.canceled.connect(lambda evt: print(f"CANCELED: {evt}"))
            recognizer.canceled.connect(canceled_cb)

            # Start continuous recognition
            print("Starting continuous pronunciation assessment...")
            logfire.info("Starting continuous recognition")
            recognizer.start_continuous_recognition()

            # Wait for completion (with timeout)
            import time
            timeout_seconds = 30
            elapsed = 0
            while not done and elapsed < timeout_seconds:
                time.sleep(0.5)  # Match Azure sample timing
                elapsed += 0.5

            # Stop recognition
            print("Stopping continuous recognition...")
            recognizer.stop_continuous_recognition()

            if recognition_error:
                raise AudioProcessingError(f"Azure recognition failed: {recognition_error}")

            if not recognized_words:
                logfire.warning("Azure: No speech recognized in continuous mode")
                return {"RecognitionStatus": "NoMatch", "DisplayText": "", "NBest": []}

            # [2.5] Manual score recalculation for better accuracy
            logfire.info(
                "Recalculating scores",
                word_count=len(recognized_words),
                fluency_scores=fluency_scores,
                prosody_scores=prosody_scores,
                durations=durations
            )

            # Process reference text for comparison
            language = config.speech_language_code
            if language.startswith('zh'):
                # Chinese text processing would go here
                # For now, use simple split
                reference_words = [w.strip(string.punctuation) for w in reference_text.lower().split()]
            else:
                reference_words = [w.strip(string.punctuation) for w in reference_text.lower().split()]

            # Use difflib to match recognized words with reference text for better miscue detection
            # Convert SDK word objects to dicts for consistent handling
            final_words = []  # List of dicts with {word, accuracy_score, error_type}

            if pronunciation_config.enable_miscue:
                diff = difflib.SequenceMatcher(
                    None,
                    reference_words,
                    [w.word.lower() for w in recognized_words]
                )

                for tag, i1, i2, j1, j2 in diff.get_opcodes():
                    if tag in ['insert', 'replace']:
                        # Mark insertions
                        for word in recognized_words[j1:j2]:
                            error_type = 'Insertion' if word.error_type == 'None' else word.error_type
                            final_words.append({
                                'word': word.word,
                                'accuracy_score': word.accuracy_score,
                                'error_type': error_type
                            })

                    if tag in ['delete', 'replace']:
                        # Mark omissions
                        for word_text in reference_words[i1:i2]:
                            final_words.append({
                                'word': word_text,
                                'accuracy_score': 0,
                                'error_type': 'Omission'
                            })

                    if tag == 'equal':
                        # Add matched words
                        for word in recognized_words[j1:j2]:
                            final_words.append({
                                'word': word.word,
                                'accuracy_score': word.accuracy_score,
                                'error_type': word.error_type
                            })
            else:
                # No miscue detection - just convert SDK objects to dicts
                final_words = [
                    {
                        'word': w.word,
                        'accuracy_score': w.accuracy_score,
                        'error_type': w.error_type
                    }
                    for w in recognized_words
                ]

            # Calculate final scores
            # Accuracy: average of non-insertion words
            final_accuracy_scores = []
            for word in final_words:
                if word['error_type'] != 'Insertion' and word['accuracy_score'] is not None:
                    final_accuracy_scores.append(word['accuracy_score'])

            accuracy_score = sum(final_accuracy_scores) / len(final_accuracy_scores) if final_accuracy_scores else 0

            # Fluency: duration-weighted average
            if durations and fluency_scores and len(durations) == len(fluency_scores):
                # Filter out None values
                valid_pairs = [(f, d) for f, d in zip(fluency_scores, durations) if f is not None and d is not None]
                if valid_pairs:
                    fluency_score = sum([x * y for (x, y) in valid_pairs]) / sum([y for (x, y) in valid_pairs])
                else:
                    fluency_score = 0
            elif fluency_scores:
                valid_fluency = [f for f in fluency_scores if f is not None]
                fluency_score = sum(valid_fluency) / len(valid_fluency) if valid_fluency else 0
            else:
                fluency_score = 0

            # Completeness: percentage of reference words spoken correctly
            # Count correct words from recognized_words (SDK objects, not final_words)
            correct_words = len([w for w in recognized_words if w.error_type == "None"])
            completeness_score = (correct_words / len(reference_words) * 100) if reference_words else 0
            completeness_score = min(completeness_score, 100)  # Cap at 100

            # Prosody: simple average (filter None values)
            valid_prosody = [p for p in prosody_scores if p is not None]
            prosody_score = sum(valid_prosody) / len(valid_prosody) if valid_prosody else 0

            # Overall pronunciation score (weighted average)
            # If prosody is 0/None, redistribute its weight to other scores
            if prosody_score == 0 or prosody_score is None:
                pron_score = (
                    accuracy_score * 0.5 +
                    fluency_score * 0.25 +
                    completeness_score * 0.25
                )
                logfire.info("Prosody unavailable, using adjusted weighting")
            else:
                pron_score = (
                    accuracy_score * 0.4 +
                    prosody_score * 0.2 +
                    fluency_score * 0.2 +
                    completeness_score * 0.2
                )

            print(f"\n{'='*80}")
            print("FINAL PARAGRAPH SCORES:")
            print(f"{'='*80}")
            print(f"    Pronunciation Score: {pron_score:.2f}")
            print(f"    Accuracy Score: {accuracy_score:.2f}")
            print(f"    Completeness Score: {completeness_score:.2f}")
            print(f"    Fluency Score: {fluency_score:.2f}")
            print(f"    Prosody Score: {prosody_score:.2f}")
            print(f"{'='*80}\n")

            logfire.info(
                "Final calculated scores",
                pronunciation_score=pron_score,
                accuracy_score=accuracy_score,
                completeness_score=completeness_score,
                fluency_score=fluency_score,
                prosody_score=prosody_score
            )

            # Build response in Azure format
            display_text = " ".join(all_recognized_texts)

            # Print word-level details (matching Azure sample)
            print(f"\nWORD-LEVEL DETAILS:")
            print(f"{'='*80}")
            for idx, word in enumerate(final_words):
                print(f"    {idx + 1}: word: {word['word']}\t"
                      f"accuracy score: {word['accuracy_score']:.2f}\t"
                      f"error type: {word['error_type']}")
            print(f"{'='*80}\n")

            # Create NBest structure - preserve phoneme data from raw JSON responses
            # Build a map of words to their full phoneme data from raw JSON
            word_phoneme_map = {}
            for json_resp in raw_json_responses:
                if 'NBest' in json_resp and len(json_resp['NBest']) > 0:
                    words_with_phonemes = json_resp['NBest'][0].get('Words', [])
                    for w in words_with_phonemes:
                        word_text = w.get('Word', '').lower()
                        # Store the full word data including Phonemes and Syllables
                        word_phoneme_map[word_text] = w
            
            words_json = []
            for word in final_words:
                word_dict = {
                    "Word": word['word'],
                    "Offset": 0,  # We don't have precise offsets in continuous mode
                    "Duration": 0,
                    "PronunciationAssessment": {
                        "AccuracyScore": word['accuracy_score'],
                        "ErrorType": word['error_type']
                    }
                }
                
                # Add phoneme and syllable data from raw JSON if available
                raw_word_data = word_phoneme_map.get(word['word'].lower())
                if raw_word_data:
                    if 'Phonemes' in raw_word_data:
                        word_dict['Phonemes'] = raw_word_data['Phonemes']
                    if 'Syllables' in raw_word_data:
                        word_dict['Syllables'] = raw_word_data['Syllables']
                
                words_json.append(word_dict)

            raw_json_response = {
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
                            "AccuracyScore": accuracy_score,
                            "FluencyScore": fluency_score,
                            "CompletenessScore": completeness_score,
                            "PronScore": pron_score,
                            "ProsodyScore": prosody_score
                        },
                        "Words": words_json
                    }
                ]
            }

            return raw_json_response

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



