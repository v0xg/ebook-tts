"""Job management service for conversion jobs."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..db.models import Job, JobStatus
from ..models.job import JobCreate, JobProgress, JobResponse
from .storage_service import StorageService


class JobService:
    """Service for managing conversion jobs."""

    def __init__(self, db: Session, storage: StorageService | None = None):
        self.db = db
        self.storage = storage

    def create_job(
        self,
        user_id: str,
        upload_key: str,
        settings: JobCreate,
    ) -> JobResponse:
        """
        Create a new conversion job.

        Args:
            user_id: ID of the user creating the job
            upload_key: S3 key of the uploaded input file
            settings: Job settings (voice, speed, output_format, etc.)
        """
        # Extract filename from upload key
        filename = Path(upload_key).name
        input_format = Path(filename).suffix.lower().lstrip(".")

        job = Job(
            id=str(uuid.uuid4()),
            user_id=user_id,
            status=JobStatus.PENDING,
            input_filename=filename,
            input_s3_key=upload_key,
            input_format=input_format,
            voice=settings.voice,
            speed=settings.speed,
            output_format=settings.output_format.value,
            chapters_to_convert=(
                json.dumps(settings.chapters_to_convert)
                if settings.chapters_to_convert
                else None
            ),
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        return self._to_response(job)

    def get_job(self, job_id: str, user_id: str) -> Optional[JobResponse]:
        """
        Get a job by ID, ensuring it belongs to the specified user.

        Returns None if job not found or doesn't belong to user.
        """
        job = (
            self.db.query(Job)
            .filter(Job.id == job_id, Job.user_id == user_id)
            .first()
        )

        if not job:
            return None

        return self._to_response(job)

    def list_jobs(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[JobResponse]:
        """List jobs for a user, ordered by creation time (newest first)."""
        jobs = (
            self.db.query(Job)
            .filter(Job.user_id == user_id)
            .order_by(Job.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [self._to_response(job) for job in jobs]

    def cancel_job(self, job_id: str, user_id: str) -> None:
        """
        Cancel a pending or processing job.

        Raises HTTPException if job not found or cannot be cancelled.
        """
        job = (
            self.db.query(Job)
            .filter(Job.id == job_id, Job.user_id == user_id)
            .first()
        )

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        if job.status not in (JobStatus.PENDING, JobStatus.PROCESSING):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel job with status: {job.status.value}",
            )

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        self.db.commit()

    def update_progress(
        self,
        job_id: str,
        stage: str,
        progress_percent: float,
        message: str,
        current_chunk: int = 0,
        total_chunks: int = 0,
    ) -> None:
        """Update job progress (called by worker)."""
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.stage = stage
            job.progress_percent = progress_percent
            job.message = message
            job.current_chunk = current_chunk
            job.total_chunks = total_chunks
            self.db.commit()

    def mark_started(self, job_id: str) -> None:
        """Mark a job as started processing."""
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
            self.db.commit()

    def mark_completed(
        self,
        job_id: str,
        output_s3_key: str,
        duration_seconds: float,
        chapters_count: int,
    ) -> None:
        """Mark a job as completed successfully."""
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.output_s3_key = output_s3_key
            job.duration_seconds = duration_seconds
            job.chapters_count = chapters_count
            job.progress_percent = 100
            self.db.commit()

    def mark_failed(self, job_id: str, error_message: str) -> None:
        """Mark a job as failed."""
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = error_message
            self.db.commit()

    def _to_response(self, job: Job) -> JobResponse:
        """Convert a Job model to JobResponse."""
        progress = JobProgress(
            status=job.status.value,
            stage=job.stage,
            progress_percent=job.progress_percent or 0,
            current_chunk=job.current_chunk or 0,
            total_chunks=job.total_chunks or 0,
            message=job.message,
        )

        # Generate download URL if completed
        download_url = None
        if job.status == JobStatus.COMPLETED and job.output_s3_key and self.storage:
            output_filename = f"{Path(job.input_filename).stem}.{job.output_format}"
            download_url = self.storage.get_download_url(
                job.output_s3_key, output_filename
            )

        return JobResponse(
            id=job.id,
            status=job.status.value,
            input_filename=job.input_filename,
            voice=job.voice,
            speed=job.speed,
            output_format=job.output_format,
            progress=progress,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=job.duration_seconds,
            chapters_count=job.chapters_count,
            error_message=job.error_message,
            download_url=download_url,
        )
