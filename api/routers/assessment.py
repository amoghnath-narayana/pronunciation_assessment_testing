"""Assessment endpoints."""

import io
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from fastapi.responses import StreamingResponse
import logfire

from api_models import AzureAssessmentResponse, ErrorResponse
from config import AppConfig
from exceptions import AssessmentError, AudioProcessingError, InvalidAssessmentResponseError
from services.gemini_service import AssessmentService

router = APIRouter(prefix="/api/v1", tags=["assessment"])


def get_assessment_service() -> AssessmentService:
    """Create assessment service instance."""
    return AssessmentService(config=AppConfig())


@router.post(
    "/assess",
    response_model=AzureAssessmentResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def assess_pronunciation(
    audio_file: Annotated[UploadFile, File(description="Audio file (WAV, 16kHz mono)")],
    expected_text: Annotated[str, Form(description="Expected sentence")],
    service: Annotated[AssessmentService, Depends(get_assessment_service)],
) -> AzureAssessmentResponse:
    """Assess pronunciation: Audio → Azure → Gemini → Response."""
    try:
        audio_data = await audio_file.read()

        if not audio_data:
            raise HTTPException(status_code=400, detail="Empty audio file")

        logfire.info("Assessment request", text=expected_text[:50], audio_bytes=len(audio_data))

        result = service.assess_pronunciation(audio_data, expected_text)

        logfire.info("Assessment complete", pron_score=result.overall_scores.pronunciation)

        return AzureAssessmentResponse.from_analysis_result(result)

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


@router.post(
    "/assess/tts",
    responses={
        200: {"content": {"audio/wav": {}}, "description": "TTS audio"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def assess_pronunciation_with_tts(
    audio_file: Annotated[UploadFile, File(description="Audio file (WAV, 16kHz mono)")],
    expected_text: Annotated[str, Form(description="Expected sentence")],
    service: Annotated[AssessmentService, Depends(get_assessment_service)],
) -> StreamingResponse:
    """Assess pronunciation and return TTS audio feedback."""
    try:
        audio_data = await audio_file.read()

        if not audio_data:
            raise HTTPException(status_code=400, detail="Empty audio file")

        logfire.info("Assessment+TTS request", text=expected_text[:50], audio_bytes=len(audio_data))

        result = service.assess_pronunciation(audio_data, expected_text)

        logfire.info("Generating TTS feedback")
        tts_audio = service.generate_tts_narration(result)

        if not tts_audio:
            raise HTTPException(status_code=500, detail="TTS generation failed")

        logfire.info("TTS complete", audio_bytes=len(tts_audio))

        return StreamingResponse(
            io.BytesIO(tts_audio),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=feedback.wav"},
        )

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
