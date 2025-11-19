"""Assessment endpoints."""

import io
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from fastapi.responses import StreamingResponse
import logfire

from api_models import AssessmentResponse, ErrorResponse
from config import AppConfig
from exceptions import (
    AssessmentError,
    AudioUploadError,
    InvalidAssessmentResponseError,
)
from services.gemini_service import GeminiAssessmentService

router = APIRouter(prefix="/api/v1", tags=["assessment"])


# Dependency to get service instance
def get_assessment_service() -> GeminiAssessmentService:
    """Create and return assessment service instance.

    Returns:
        GeminiAssessmentService: Configured assessment service
    """
    config = AppConfig()
    return GeminiAssessmentService(config=config)


@router.post(
    "/assess",
    response_model=AssessmentResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def assess_pronunciation(
    audio_file: Annotated[
        UploadFile, File(description="Audio file (WAV, MP3, or PCM)")
    ],
    expected_text: Annotated[str, Form(description="Expected sentence text")],
    service: Annotated[GeminiAssessmentService, Depends(get_assessment_service)],
) -> AssessmentResponse:
    """Assess pronunciation from uploaded audio.

    Accepts an audio file and expected text, returns detailed pronunciation assessment.

    Args:
        audio_file: Uploaded audio file
        expected_text: Expected sentence text to compare against
        service: Assessment service (injected)

    Returns:
        AssessmentResponse: Detailed assessment with scores and feedback

    Raises:
        HTTPException: If assessment fails
    """
    try:
        # Read audio file
        audio_data = await audio_file.read()

        if not audio_data:
            raise HTTPException(status_code=400, detail="Empty audio file")

        logfire.info(
            f"Processing assessment request for text: '{expected_text}', "
            f"audio size: {len(audio_data)} bytes"
        )

        # Perform assessment
        result = service.assess_pronunciation(
            audio_data_bytes=audio_data, expected_sentence_text=expected_text
        )

        logfire.info(
            f"Assessment completed. Found {len(result.specific_errors)} errors"
        )

        return AssessmentResponse(assessment=result)

    except AudioUploadError as e:
        logfire.error(f"Audio upload failed: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e

    except InvalidAssessmentResponseError as e:
        logfire.error(f"Invalid assessment response: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    except AssessmentError as e:
        logfire.error(f"Assessment error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    except Exception as e:
        logfire.exception(f"Unexpected error during assessment: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post(
    "/assess/tts",
    responses={
        200: {
            "content": {"audio/wav": {}},
            "description": "TTS narration audio (WAV format)",
        },
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def assess_pronunciation_with_tts(
    audio_file: Annotated[
        UploadFile, File(description="Audio file (WAV, MP3, or PCM)")
    ],
    expected_text: Annotated[str, Form(description="Expected sentence text")],
    service: Annotated[GeminiAssessmentService, Depends(get_assessment_service)],
) -> StreamingResponse:
    """Assess pronunciation and generate TTS narration.

    Combines assessment with TTS generation in a single request.
    Returns audio narration of the assessment results.

    Args:
        audio_file: Uploaded audio file
        expected_text: Expected sentence text to compare against
        service: Assessment service (injected)

    Returns:
        StreamingResponse: TTS narration audio (WAV format)

    Raises:
        HTTPException: If assessment or TTS generation fails
    """
    try:
        # Read audio file
        audio_data = await audio_file.read()

        if not audio_data:
            raise HTTPException(status_code=400, detail="Empty audio file")

        logfire.info(
            f"Processing assessment + TTS request for text: '{expected_text}', "
            f"audio size: {len(audio_data)} bytes"
        )

        # Perform assessment
        result = service.assess_pronunciation(
            audio_data_bytes=audio_data, expected_sentence_text=expected_text
        )

        logfire.info("Assessment completed. Generating TTS narration...")

        # Generate TTS narration
        tts_audio = service.generate_tts_narration(result)

        if not tts_audio:
            raise HTTPException(status_code=500, detail="TTS generation failed")

        logfire.info(f"TTS narration generated. Size: {len(tts_audio)} bytes")

        # Return as streaming audio
        return StreamingResponse(
            io.BytesIO(tts_audio),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=assessment_narration.wav"
            },
        )

    except AudioUploadError as e:
        logfire.error(f"Audio upload failed: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e

    except InvalidAssessmentResponseError as e:
        logfire.error(f"Invalid assessment response: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    except AssessmentError as e:
        logfire.error(f"Assessment error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    except Exception as e:
        logfire.exception(f"Unexpected error during assessment + TTS: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
