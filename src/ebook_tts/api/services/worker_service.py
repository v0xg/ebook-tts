"""Background worker service for processing conversion jobs."""

import json
import logging
import os
import tempfile
from pathlib import Path

from ..config import get_settings
from ..db.database import SessionLocal
from ..db.models import Job, JobStatus
from .job_service import JobService
from .storage_service import StorageService

logger = logging.getLogger(__name__)


class WorkerService:
    """Service for processing conversion jobs in the background."""

    @staticmethod
    def process_job(job_id: str) -> None:
        """
        Process a conversion job.

        This runs as a background task and handles:
        1. Downloading input file from S3
        2. Running the TTS conversion
        3. Uploading output to S3
        4. Updating job status throughout
        """
        settings = get_settings()
        db = SessionLocal()
        storage = StorageService(settings)
        job_service = JobService(db, storage)

        try:
            # Get job from database
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            if job.status != JobStatus.PENDING:
                logger.warning(f"Job {job_id} is not pending, skipping")
                return

            # Mark as processing
            job_service.mark_started(job_id)
            logger.info(f"Starting job {job_id}")

            # Create temp directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Download input file from S3
                input_suffix = Path(job.input_s3_key).suffix
                input_path = temp_path / f"input{input_suffix}"

                logger.info(f"Downloading input file for job {job_id}")
                storage.download_to_file(job.input_s3_key, input_path)

                # Set up output path
                output_filename = f"{Path(job.input_filename).stem}.{job.output_format}"
                output_path = temp_path / output_filename

                # Parse chapters if specified
                chapters_to_convert = None
                if job.chapters_to_convert:
                    chapters_to_convert = json.loads(job.chapters_to_convert)

                # Create progress callback that updates DB
                def progress_callback(update):
                    job_service.update_progress(
                        job_id=job_id,
                        stage=update.stage,
                        progress_percent=update.percent,
                        message=update.message,
                        current_chunk=update.chunks_completed,
                        total_chunks=update.chunks_total,
                    )

                # Force CPU mode by hiding CUDA devices if configured for CPU
                if settings.tts_device == "cpu":
                    os.environ["CUDA_VISIBLE_DEVICES"] = ""

                # Import here to avoid loading TTS model at module import
                from ...converter import PDFToAudiobook

                # Run conversion
                logger.info(f"Starting conversion for job {job_id}")
                converter = PDFToAudiobook(
                    progress_callback=progress_callback,
                    device=settings.tts_device,
                    voice=job.voice,
                    chunk_size=settings.default_chunk_size,
                )

                result = converter.convert(
                    input_path=str(input_path),
                    output_path=str(output_path),
                    chapters_to_convert=chapters_to_convert,
                    speed=job.speed,
                )

                # Upload output to S3
                output_key = f"outputs/{job.user_id}/{job.id}/{output_filename}"
                logger.info(f"Uploading output for job {job_id}")
                storage.upload_file(output_path, output_key)

                # Mark job as completed
                job_service.mark_completed(
                    job_id=job_id,
                    output_s3_key=output_key,
                    duration_seconds=result.duration_seconds,
                    chapters_count=len(result.chapters),
                )

                logger.info(
                    f"Job {job_id} completed successfully. "
                    f"Duration: {result.duration_seconds:.1f}s"
                )

        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")
            job_service.mark_failed(job_id, str(e))

        finally:
            db.close()
