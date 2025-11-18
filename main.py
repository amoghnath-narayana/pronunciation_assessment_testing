"""FastAPI application for pronunciation assessment."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logfire

from api.routers import assessment, health
from constants import APIConfig
from exceptions import AssessmentError


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logfire.info("Starting Pronunciation Assessment API")
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
    logfire.info(f"{request.method} {request.url.path} completed in {process_time:.3f}s")

    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handler for custom exceptions
@app.exception_handler(AssessmentError)
async def assessment_error_handler(request: Request, exc: AssessmentError):
    """Handle custom assessment errors."""
    logfire.error(f"Assessment error: {exc.message}", details=exc.details)
    return JSONResponse(
        status_code=500,
        content={"error": exc.__class__.__name__, "message": exc.message, "details": exc.details},
    )


# Include routers
app.include_router(health.router)
app.include_router(assessment.router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": APIConfig.TITLE,
        "version": APIConfig.VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


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
