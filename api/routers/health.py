"""Health check endpoint."""

from fastapi import APIRouter

from api_models import HealthCheckResponse
from constants import APIConfig

router = APIRouter(tags=["health"])
__all__ = ["router", "health_check"]


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Check if the API is running and healthy."""
    return HealthCheckResponse(status="healthy", version=APIConfig.VERSION)
