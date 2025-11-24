"""
Assessment API Endpoints.

Flow:
    [1] POST /api/v1/assess - Pronunciation assessment endpoint
        - Receives: audio_file (WebM/WAV) + expected_text
        - Returns: JSON scores and feedback
        - Calls: Azure Speech → Gemini Analysis

Optimization Notes:
    - Singleton service pattern eliminates per-request initialization (~50-200ms saved)
"""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, Depends
import logfire

from models.api_models import AssessmentResponse, ErrorResponse
from config import AppConfig
from exceptions import AudioProcessingError
from services.gemini_service import AssessmentService

router = APIRouter(prefix="/api/v1", tags=["assessment"])


@lru_cache(maxsize=1)
def get_assessment_service() -> AssessmentService:
    """
    Get singleton AssessmentService (cached via @lru_cache).

    FastAPI's dependency injection + lru_cache ensures single instance.
    Avoids repeated initialization of:
        - Config parsing
        - TTS asset loading
        - Diskcache setup
        - Gemini client

    Returns:
        AssessmentService: Singleton service instance
    """
    logfire.info("Initializing singleton AssessmentService")
    config = AppConfig()
    service = AssessmentService(config=config)
    logfire.info("Singleton AssessmentService ready")
    return service


@router.post(
    "/assess",
    response_model=AssessmentResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def assess_pronunciation(
    audio_file: Annotated[UploadFile, File(description="Audio file (WebM/WAV)")],
    expected_text: Annotated[str, Form(description="Expected sentence")],
    service: Annotated[AssessmentService, Depends(get_assessment_service)] = None,
) -> AssessmentResponse:
    """
    Main assessment endpoint - processes audio and returns scores.

    Pipeline:
        [1.1] Receive audio file and expected text from frontend
        [1.2] Call Azure Speech Pronunciation Assessment API
        [1.3] Call Gemini for learner-friendly feedback
        [1.4] Return response with scores and feedback

    Args:
        audio_file: Recorded audio (WebM from browser or WAV)
        expected_text: The sentence the user was supposed to read
        service: Singleton AssessmentService instance

    Returns:
        AssessmentResponse: Scores and feedback
    """
    audio_data = await audio_file.read()

    if not audio_data:
        raise AudioProcessingError("Empty audio file")

    logfire.info(
        "Assessment request",
        text=expected_text[:50],
        audio_bytes=len(audio_data),
    )

    # Azure assessment + Gemini analysis
    result = await service.assess_pronunciation_async(audio_data, expected_text)

    logfire.info("Assessment complete", pron_score=result.overall_scores.pronunciation)

    return AssessmentResponse.from_analysis_result(result)
