"""Pydantic models for conversion jobs."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    """Supported audio output formats."""

    WAV = "wav"
    MP3 = "mp3"
    M4B = "m4b"


class JobCreate(BaseModel):
    """Request model for creating a conversion job."""

    voice: str = "af_heart"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    output_format: OutputFormat = OutputFormat.MP3
    chapters_to_convert: Optional[list[int]] = None


class JobProgress(BaseModel):
    """Progress information for a conversion job."""

    status: str
    stage: Optional[str] = None
    progress_percent: float = 0
    current_chunk: int = 0
    total_chunks: int = 0
    message: Optional[str] = None


class JobResponse(BaseModel):
    """Response model for a conversion job."""

    id: str
    status: str
    input_filename: str
    voice: str
    speed: float
    output_format: str
    progress: JobProgress
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    chapters_count: Optional[int] = None
    error_message: Optional[str] = None
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    """Response model for file upload URL."""

    upload_url: str
    upload_key: str
    expires_in: int  # seconds
