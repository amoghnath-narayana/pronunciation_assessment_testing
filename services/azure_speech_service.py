"""Azure Speech Pronunciation Assessment service."""

import base64
import json
import os
from dataclasses import dataclass
from typing import Any

import httpx
import logfire

from exceptions import ConfigurationError, AudioProcessingError


@dataclass
class AzureSpeechConfig:
    """Configuration for Azure Speech service."""

    speech_key: str
    speech_region: str
    language_code: str = "en-IN"

    @classmethod
    def from_env(cls) -> "AzureSpeechConfig":
        """Load configuration from environment variables.

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


def assess_pronunciation_with_azure(
    audio_bytes: bytes,
    reference_text: str,
    language_code: str = "en-IN",
    config: AzureSpeechConfig | None = None,
) -> dict[str, Any]:
    """Assess pronunciation using Azure Speech Pronunciation Assessment API.

    Sends audio to Azure Speech service and returns detailed pronunciation scores
    including word-level and phoneme-level analysis with prosody assessment.

    Args:
        audio_bytes: Raw WAV audio bytes (16kHz mono PCM format)
        reference_text: The expected sentence the user should have spoken
        language_code: Language code for assessment (default: "en-IN" for Indian English)
        config: Azure Speech configuration. If None, loads from environment variables.

    Returns:
        dict: Azure assessment result containing:
            - RecognitionStatus: Success/failure status
            - NBest[0].PronunciationAssessment: Overall scores (PronScore, AccuracyScore, etc.)
            - NBest[0].Words: Per-word scores with phoneme details
            - NBest[0].PronunciationAssessment.Feedback.Prosody: Prosody feedback

    Raises:
        ConfigurationError: If Azure credentials are missing
        AudioProcessingError: If audio_bytes is empty or API call fails

    Example:
        >>> result = assess_pronunciation_with_azure(
        ...     audio_bytes=wav_data,
        ...     reference_text="The cat is on the mat"
        ... )
        >>> print(result["NBest"][0]["PronunciationAssessment"]["PronScore"])
        85.2
    """
    # Guard clauses
    if not audio_bytes:
        raise AudioProcessingError("audio_bytes cannot be empty")

    if not reference_text or not reference_text.strip():
        raise AudioProcessingError("reference_text cannot be empty")

    if config is None:
        config = AzureSpeechConfig.from_env()

    # Build pronunciation assessment configuration
    pronunciation_config = {
        "ReferenceText": reference_text.strip(),
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "Dimension": "Comprehensive",
        "EnableProsodyAssessment": True,
    }

    # Base64 encode the config for header
    encoded_config = base64.b64encode(
        json.dumps(pronunciation_config).encode("utf-8")
    ).decode("utf-8")

    # Build request
    endpoint_url = (
        f"https://{config.speech_region}.stt.speech.microsoft.com"
        f"/speech/recognition/conversation/cognitiveservices/v1"
        f"?language={language_code}&format=detailed"
    )

    headers = {
        "Accept": "application/json;text/xml",
        "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
        "Ocp-Apim-Subscription-Key": config.speech_key,
        "Pronunciation-Assessment": encoded_config,
    }

    logfire.info(
        "Sending audio to Azure Speech for pronunciation assessment",
        audio_size_bytes=len(audio_bytes),
        reference_text=reference_text[:50] + "..." if len(reference_text) > 50 else reference_text,
        language=language_code,
    )

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                endpoint_url,
                headers=headers,
                content=audio_bytes,
            )

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No error details"
            logfire.error(
                "Azure Speech API error",
                status_code=response.status_code,
                error=error_detail,
            )
            raise AudioProcessingError(
                f"Azure Speech API returned status {response.status_code}: {error_detail}"
            )

        result = response.json()

        # Log success metrics
        recognition_status = result.get("RecognitionStatus", "Unknown")
        if recognition_status == "Success" and result.get("NBest"):
            assessment = result["NBest"][0].get("PronunciationAssessment", {})
            logfire.info(
                "Azure pronunciation assessment completed",
                recognition_status=recognition_status,
                pron_score=assessment.get("PronScore"),
                accuracy_score=assessment.get("AccuracyScore"),
                fluency_score=assessment.get("FluencyScore"),
                completeness_score=assessment.get("CompletenessScore"),
                prosody_score=assessment.get("ProsodyScore"),
            )
        else:
            logfire.warning(
                "Azure assessment returned non-success status",
                recognition_status=recognition_status,
            )

        return result

    except httpx.TimeoutException as e:
        logfire.error("Azure Speech API timeout", error=str(e))
        raise AudioProcessingError("Azure Speech API request timed out") from e
    except httpx.RequestError as e:
        logfire.error("Azure Speech API request error", error=str(e))
        raise AudioProcessingError(f"Azure Speech API request failed: {e}") from e
    except json.JSONDecodeError as e:
        logfire.error("Failed to parse Azure response", error=str(e))
        raise AudioProcessingError("Invalid JSON response from Azure Speech API") from e


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
