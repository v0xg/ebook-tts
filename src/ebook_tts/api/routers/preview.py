"""Preview router for chapter detection and text preview."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..db.models import User
from ..dependencies import get_current_user
from ..models.voice import ChapterInfo, ChaptersResponse, PreviewResponse
from ..services.storage_service import StorageService, get_storage_service

router = APIRouter(prefix="/preview", tags=["Preview"])


@router.post(
    "/chapters",
    response_model=ChaptersResponse,
    summary="Detect chapters",
)
def detect_chapters(
    upload_key: str,
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
):
    """
    Detect chapters in an uploaded ebook file.

    Use this after uploading a file to see what chapters are available.
    You can then specify which chapters to convert when creating a job.
    """
    # Verify file exists
    if not storage.file_exists(upload_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file not found",
        )

    # Download file temporarily
    local_path = storage.download_to_temp(upload_key)

    try:
        # Import here to avoid loading TTS model at module import
        from ...converter import PDFToAudiobook

        # Use mock TTS to avoid loading the model
        converter = PDFToAudiobook(mock_tts=True, device="cpu")
        chapters = converter.extract_chapters(str(local_path))

        return ChaptersResponse(
            chapters=[
                ChapterInfo(
                    number=i,
                    title=ch.title,
                    start_page=ch.start_page,
                )
                for i, ch in enumerate(chapters, 1)
            ],
            total=len(chapters),
        )

    finally:
        # Clean up temp file (but not in local storage mode)
        if not storage._use_local:
            local_path.unlink(missing_ok=True)


@router.post(
    "/text",
    response_model=PreviewResponse,
    summary="Preview processed text",
)
def preview_text(
    upload_key: str,
    max_chars: int = Query(
        default=1000,
        le=5000,
        description="Maximum characters to return (max 5000)",
    ),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
):
    """
    Preview how text will be processed for TTS.

    Shows the cleaned and preprocessed text that will be sent to the
    TTS engine, including:
    - Ligature expansion
    - Smart quote normalization
    - Abbreviation expansion
    - Language detection
    """
    # Verify file exists
    if not storage.file_exists(upload_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file not found",
        )

    # Download file temporarily
    local_path = storage.download_to_temp(upload_key)

    try:
        # Import here to avoid loading TTS model at module import
        from ...converter import PDFToAudiobook

        # Use mock TTS to avoid loading the model
        converter = PDFToAudiobook(mock_tts=True, device="cpu")

        # Get preprocessed text
        text = converter.preview_text(str(local_path), max_chars=max_chars)
        detected_language = converter.preprocessor.detected_language or "unknown"

        # Estimate total chars (we can't get exact without processing the whole doc)
        # The preview_text method truncates, so we report what we have
        total_chars = len(text)
        if text.endswith("..."):
            total_chars = -1  # Indicate truncated

        return PreviewResponse(
            text=text,
            detected_language=detected_language,
            total_chars=total_chars,
        )

    finally:
        # Clean up temp file (but not in local storage mode)
        if not storage._use_local:
            local_path.unlink(missing_ok=True)
