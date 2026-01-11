"""Pydantic models for voice-related endpoints."""

from typing import Optional

from pydantic import BaseModel


class VoiceInfo(BaseModel):
    """Information about a TTS voice."""

    name: str
    description: str
    language_code: str
    language_name: str


class VoiceListResponse(BaseModel):
    """Response model for voice listing."""

    voices: list[VoiceInfo]
    by_language: dict[str, list[VoiceInfo]]


class ChapterInfo(BaseModel):
    """Information about a detected chapter."""

    number: int
    title: str
    start_page: Optional[int] = None


class ChaptersResponse(BaseModel):
    """Response model for chapter detection."""

    chapters: list[ChapterInfo]
    total: int


class PreviewResponse(BaseModel):
    """Response model for text preview."""

    text: str
    detected_language: str
    total_chars: int
