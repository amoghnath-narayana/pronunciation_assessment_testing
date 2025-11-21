"""FastAPI application for pronunciation assessment."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import logfire

from api.routers.assessment import router as assessment_router
from api.routers.health import router as health_router
from constants import APIConfig
from exceptions import AssessmentError

__all__ = [
    "app",
    "log_requests",
    "assessment_error_handler",
    "global_exception_handler",
    "root",
    "chrome_devtools",
]


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan events.

    Startup:
        [1] Pre-warm HTTP clients for faster first request
        [2] Initialize singleton services
    """
    # Startup
    logfire.info("Starting Pronunciation Assessment API")

    # [1] Pre-warm HTTP client connections (~50-100ms saved on first request)
    from services.azure_speech_service import warmup_http_client

    await warmup_http_client()

    # [2] Initialize singleton AssessmentService early
    from api.routers.assessment import get_assessment_service

    get_assessment_service()
    logfire.info("Services initialized and ready")

    yield

    # Shutdown
    logfire.info("Shutting down Pronunciation Assessment API")


# Create FastAPI app
app = FastAPI(
    title=APIConfig.TITLE,
    description=APIConfig.DESCRIPTION,
    version=APIConfig.VERSION,
    lifespan=lifespan,
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing information."""
    start_time = time.time()

    # Log request
    logfire.info(f"{request.method} {request.url.path}")

    # Process request
    response = await call_next(request)

    # Log response time
    process_time = time.time() - start_time
    logfire.info(
        f"{request.method} {request.url.path} completed in {process_time:.3f}s"
    )

    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handler for custom exceptions
@app.exception_handler(AssessmentError)
async def assessment_error_handler(request: Request, exc: AssessmentError):
    """Handle custom assessment errors."""
    logfire.exception(f"Assessment error: {exc.message}", details=exc.details)
    return JSONResponse(
        status_code=500,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
        },
    )


# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logfire.exception(
        f"Unhandled exception in {request.method} {request.url.path}: {exc}"
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
        },
    )


# Mount static files
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(assessment_router)


# Root endpoint - Serve index.html
@app.get("/")
async def root():
    """Serve the frontend application."""
    return FileResponse("static/index.html")


# Handle Chrome DevTools request
@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools():
    """Return empty JSON for Chrome DevTools request."""
    return JSONResponse(content={})


if __name__ == "__main__":
    import uvicorn

    # Configure logfire for local development
    logfire.configure()

    uvicorn.run(
        "main:app",
        host=APIConfig.DEFAULT_HOST,
        port=APIConfig.DEFAULT_PORT,
        reload=True,
        log_level="info",
    )
