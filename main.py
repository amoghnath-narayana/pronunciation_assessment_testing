"""FastAPI application for pronunciation assessment."""

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
    "assessment_error_handler",
    "global_exception_handler",
    "root",
    "chrome_devtools",
]


# Create FastAPI app (dependency injection handles singleton initialization)
app = FastAPI(
    title=APIConfig.TITLE,
    description=APIConfig.DESCRIPTION,
    version=APIConfig.VERSION,
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    uvicorn.run(
        "main:app",
        host=APIConfig.DEFAULT_HOST,
        port=APIConfig.DEFAULT_PORT,
        reload=True,
        log_level="info",
    )
