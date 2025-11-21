"""
Assessment API Endpoints.

Flow:
    [1] POST /api/v1/assess - Single endpoint for pronunciation assessment
        - Receives: audio_file (WebM/WAV) + expected_text + include_tts (optional)
        - Returns: JSON scores + optional base64 TTS audio
        - Calls: Azure Speech → Gemini Analysis → TTS Generation (if requested)

Optimization Notes:
    - Singleton service pattern eliminates per-request initialization (~50-200ms saved)
    - Single endpoint eliminates duplicate Azure+Gemini calls (~1.5-2.5s saved)
    - High score shortcut skips Gemini for scores > 90 (~500-1000ms saved)
"""

import base64
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
import logfire

from api_models import AssessmentWithTTSResponse, ErrorResponse
from config import AppConfig
from exceptions import (
    AssessmentError,
    AudioProcessingError,
    InvalidAssessmentResponseError,
)
from services.gemini_service import AssessmentService

router = APIRouter(prefix="/api/v1", tags=["assessment"])


# -----------------------------------------------------------------------------
# [OPTIMIZATION] Singleton Service Pattern
# -----------------------------------------------------------------------------
# Previously: AssessmentService created per request (~50-200ms overhead)
# Now: Single instance shared across all requests
# -----------------------------------------------------------------------------
_assessment_service: AssessmentService | None = None
_app_config: AppConfig | None = None


def get_assessment_service() -> AssessmentService:
    """
    Step 0: Get or create singleton AssessmentService.

    Returns cached service instance to avoid:
        - Repeated .env parsing
        - TTS asset manifest loading
        - Diskcache initialization
        - Gemini client creation

    Returns:
        AssessmentService: Singleton service instance
    """
    global _assessment_service, _app_config

    if _assessment_service is None:
        logfire.info("Initializing singleton AssessmentService")
        _app_config = AppConfig()
        _assessment_service = AssessmentService(config=_app_config)
        logfire.info("Singleton AssessmentService ready")

    return _assessment_service


@router.post(
    "/assess",
    response_model=AssessmentWithTTSResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def assess_pronunciation(
    audio_file: Annotated[UploadFile, File(description="Audio file (WebM/WAV)")],
    expected_text: Annotated[str, Form(description="Expected sentence")],
    include_tts: Annotated[
        bool, Form(description="Include TTS audio in response")
    ] = True,
    service: Annotated[AssessmentService, Depends(get_assessment_service)] = None,
) -> AssessmentWithTTSResponse:
    """
    Step 1: Main assessment endpoint - processes audio and returns scores + optional TTS.

    Pipeline:
        [1.1] Receive audio file and expected text from frontend
        [1.2] Call Azure Speech Pronunciation Assessment API
        [1.3] If score >= 90: Use template response (skip Gemini)
        [1.4] If score < 90: Call Gemini for learner-friendly feedback
        [1.5] If include_tts=True: Generate TTS audio feedback
        [1.6] Return combined response with scores and base64 TTS audio

    Args:
        audio_file: Recorded audio (WebM from browser or WAV)
        expected_text: The sentence the user was supposed to read
        include_tts: Whether to generate TTS audio feedback (default: True)
        service: Singleton AssessmentService instance

    Returns:
        AssessmentWithTTSResponse: Scores, feedback, and optional base64 TTS audio

    Optimization:
        - Single endpoint eliminates duplicate Azure+Gemini calls (~1.5-2.5s saved)
        - High score shortcut skips Gemini when not needed (~500-1000ms saved)
    """
    try:
        audio_data = await audio_file.read()

        if not audio_data:
            raise HTTPException(status_code=400, detail="Empty audio file")

        logfire.info(
            "Assessment request",
            text=expected_text[:50],
            audio_bytes=len(audio_data),
            include_tts=include_tts,
        )

        # Step 1.2-1.4: Azure assessment + Gemini analysis (with high score shortcut)
        result = await service.assess_pronunciation_async(audio_data, expected_text)

        logfire.info(
            "Assessment complete", pron_score=result.overall_scores.pronunciation
        )

        # Step 1.5: Generate TTS if requested (async for non-blocking)
        tts_audio_base64 = None
        if include_tts:
            logfire.info("Generating TTS feedback (async)")
            tts_audio = await service.generate_tts_narration_async(result)
            if tts_audio:
                tts_audio_base64 = base64.b64encode(tts_audio).decode("utf-8")
                logfire.info("TTS complete", audio_bytes=len(tts_audio))

        # Step 1.6: Return combined response
        return AssessmentWithTTSResponse.from_analysis_result(result, tts_audio_base64)

    except AudioProcessingError as e:
        logfire.error("Audio processing error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InvalidAssessmentResponseError as e:
        logfire.error("Invalid response", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
    except AssessmentError as e:
        logfire.error("Assessment error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        logfire.exception("Unexpected error")
        raise HTTPException(status_code=500, detail="Internal server error") from e
