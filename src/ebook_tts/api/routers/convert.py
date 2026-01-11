"""Conversion router for ebook-to-audiobook conversion jobs."""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.models import User
from ..dependencies import get_current_user, get_db
from ..models.job import JobCreate, JobResponse, UploadResponse
from ..services.job_service import JobService
from ..services.storage_service import StorageService, get_storage_service
from ..services.worker_service import WorkerService

router = APIRouter(prefix="/convert", tags=["Conversion"])


@router.get(
    "/upload",
    response_model=UploadResponse,
    summary="Get upload URL",
)
def get_upload_url(
    filename: str = Query(..., description="Name of the file to upload"),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
):
    """
    Get a pre-signed URL for uploading an ebook file directly to storage.

    Supported formats: PDF, EPUB

    The client should PUT the file directly to the returned `upload_url`.
    Save the `upload_key` to use when creating a conversion job.
    """
    # Validate filename extension
    lower_filename = filename.lower()
    if not (lower_filename.endswith(".pdf") or lower_filename.endswith(".epub")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and EPUB files are supported",
        )

    return storage.get_upload_url(user_id=current_user.id, filename=filename)


@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start conversion job",
)
def create_conversion_job(
    upload_key: str,
    job_settings: JobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
):
    """
    Start a new ebook-to-audiobook conversion job.

    Workflow:
    1. Call GET /upload to get a pre-signed upload URL
    2. PUT the ebook file to that URL
    3. Call this endpoint with the `upload_key` to start conversion
    4. Poll GET /jobs/{id} for progress

    Parameters:
    - **upload_key**: The S3 key returned from the upload step
    - **voice**: TTS voice to use (default: af_heart)
    - **speed**: Speech speed multiplier, 0.5-2.0 (default: 1.0)
    - **output_format**: wav, mp3, or m4b (default: mp3)
    - **chapters_to_convert**: Optional list of chapter numbers to convert
    """
    # Verify file exists in storage
    if not storage.file_exists(upload_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file not found. Please upload first using GET /upload.",
        )

    # Create job in database
    job_service = JobService(db, storage)
    job = job_service.create_job(
        user_id=current_user.id,
        upload_key=upload_key,
        settings=job_settings,
    )

    # Queue background processing
    background_tasks.add_task(WorkerService.process_job, job.id)

    return job


@router.get(
    "/jobs",
    response_model=list[JobResponse],
    summary="List jobs",
)
def list_jobs(
    limit: int = Query(default=20, le=100, description="Maximum number of jobs"),
    offset: int = Query(default=0, ge=0, description="Number of jobs to skip"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
):
    """List the current user's conversion jobs, newest first."""
    job_service = JobService(db, storage)
    return job_service.list_jobs(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
):
    """
    Get the status and progress of a conversion job.

    Poll this endpoint to track conversion progress.
    When status is "completed", use the `download_url` to get the audio file.
    """
    job_service = JobService(db, storage)
    job = job_service.get_job(job_id, current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return job


@router.get(
    "/jobs/{job_id}/download",
    summary="Get download URL",
)
def get_download_url(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
):
    """
    Get a pre-signed download URL for a completed conversion.

    Returns a URL that can be used to download the audio file directly.
    The URL expires after 24 hours.
    """
    job_service = JobService(db, storage)
    job = job_service.get_job(job_id, current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed. Current status: {job.status}",
        )

    if not job.download_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file not found",
        )

    return {"download_url": job.download_url}


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel job",
)
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a pending or processing job.

    Only jobs with status "pending" or "processing" can be cancelled.
    """
    job_service = JobService(db)
    job_service.cancel_job(job_id, current_user.id)


# === Local storage endpoints (for development/testing without S3) ===


@router.post(
    "/upload-local/{upload_key:path}",
    summary="Upload file (local storage)",
)
async def upload_local(
    upload_key: str,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
):
    """
    Upload a file directly to local storage (development mode only).

    This endpoint is used when S3 is not configured.
    """
    if not storage._use_local:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local upload not available. Use S3 pre-signed URL instead.",
        )

    content = await file.read()
    storage.save_upload(upload_key, content)
    return {"status": "uploaded", "key": upload_key}


@router.get(
    "/download-local/{file_key:path}",
    summary="Download file (local storage)",
)
def download_local(
    file_key: str,
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
):
    """
    Download a file from local storage (development mode only).
    """
    if not storage._use_local:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local download not available. Use S3 pre-signed URL instead.",
        )

    settings = get_settings()
    file_path = Path(settings.local_storage_path) / file_key

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return FileResponse(file_path, filename=file_path.name)
