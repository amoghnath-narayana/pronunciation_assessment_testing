"""Health check endpoint."""

from fastapi import APIRouter

from api_models import HealthCheckResponse
from constants import APIConfig

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Check if the API is running and healthy.

    Returns:
        HealthCheckResponse: Service health status and version
    """
    return HealthCheckResponse(status="healthy", version=APIConfig.VERSION)
