"""FastAPI application for ebook-tts REST API."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db.database import Base, engine
from .routers import auth, convert, preview, voices

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup: Create database tables
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

    yield

    # Shutdown: cleanup if needed
    logger.info("Shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ebook-tts API",
        description=(
            "Convert ebooks (PDF/EPUB) to audiobooks using Kokoro TTS.\n\n"
            "## Features\n"
            "- 54 pre-built voices in multiple languages\n"
            "- Background processing with progress tracking\n"
            "- Chapter detection and selective conversion\n"
            "- Multiple output formats: WAV, MP3, M4B\n\n"
            "## Quick Start\n"
            "1. Register an account at `/api/v1/auth/register`\n"
            "2. Login to get tokens at `/api/v1/auth/login`\n"
            "3. Get upload URL at `/api/v1/convert/upload`\n"
            "4. PUT your ebook file to the upload URL\n"
            "5. Start conversion at `/api/v1/convert`\n"
            "6. Poll for progress at `/api/v1/convert/jobs/{id}`\n"
            "7. Download result when complete"
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else "/docs",
        redoc_url="/redoc" if settings.debug else "/redoc",
        openapi_url="/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # Include routers
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(convert.router, prefix="/api/v1")
    app.include_router(voices.router, prefix="/api/v1")
    app.include_router(preview.router, prefix="/api/v1")

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Health check endpoint for monitoring and load balancers."""
        return {"status": "healthy"}

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "ebook-tts API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }

    return app


# Create the application instance
app = create_app()
