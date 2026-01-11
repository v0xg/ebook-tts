"""S3-compatible storage service for file uploads and downloads."""

import shutil
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ..config import Settings, get_settings


class StorageService:
    """Service for S3-compatible object storage operations."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client: Optional[boto3.client] = None
        self._use_local = self.settings.use_local_storage or not self.settings.s3_configured

        if self._use_local:
            # Create local storage directory
            self._local_path = Path(self.settings.local_storage_path)
            self._local_path.mkdir(parents=True, exist_ok=True)

    @property
    def client(self):
        """Lazy-initialize S3 client."""
        if self._use_local:
            raise RuntimeError("S3 client not available in local storage mode")

        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.s3_endpoint_url,
                aws_access_key_id=self.settings.s3_access_key_id,
                aws_secret_access_key=self.settings.s3_secret_access_key,
                region_name=self.settings.s3_region,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    @property
    def bucket(self) -> str:
        """Get the configured bucket name."""
        return self.settings.s3_bucket_name

    def get_upload_url(self, user_id: str, filename: str) -> dict:
        """
        Generate a pre-signed URL for client-side file upload.

        Returns:
            dict with upload_url, upload_key, and expires_in
        """
        # Create unique key: uploads/{user_id}/{uuid}/{filename}
        key = f"uploads/{user_id}/{uuid.uuid4()}/{filename}"

        if self._use_local:
            # For local storage, return a direct upload endpoint
            return {
                "upload_url": f"/api/v1/convert/upload-local/{key}",
                "upload_key": key,
                "expires_in": self.settings.upload_url_expire_seconds,
            }

        url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": self._get_content_type(filename),
            },
            ExpiresIn=self.settings.upload_url_expire_seconds,
        )

        return {
            "upload_url": url,
            "upload_key": key,
            "expires_in": self.settings.upload_url_expire_seconds,
        }

    def get_download_url(self, key: str, filename: str | None = None) -> str:
        """
        Generate a pre-signed URL for downloading a file.

        Args:
            key: S3 object key
            filename: Optional filename for Content-Disposition header
        """
        if self._use_local:
            # For local storage, return a direct download endpoint
            return f"/api/v1/convert/download-local/{key}"

        params = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        return self.client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=self.settings.download_url_expire_seconds,
        )

    def file_exists(self, key: str) -> bool:
        """Check if a file exists in storage."""
        if self._use_local:
            return (self._local_path / key).exists()

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def download_to_temp(self, key: str) -> Path:
        """
        Download a file to a temporary location.

        Returns:
            Path to the temporary file (caller must delete when done)
        """
        if self._use_local:
            # For local storage, just return the path directly
            local_file = self._local_path / key
            if not local_file.exists():
                raise FileNotFoundError(f"File not found: {key}")
            return local_file

        suffix = Path(key).suffix
        temp_file = NamedTemporaryFile(suffix=suffix, delete=False)

        try:
            self.client.download_fileobj(self.bucket, key, temp_file)
            temp_file.close()
            return Path(temp_file.name)
        except Exception:
            temp_file.close()
            Path(temp_file.name).unlink(missing_ok=True)
            raise

    def download_to_file(self, key: str, local_path: Path) -> None:
        """Download a file to a specific local path."""
        if self._use_local:
            source = self._local_path / key
            shutil.copy2(source, local_path)
            return

        self.client.download_file(self.bucket, key, str(local_path))

    def upload_file(self, local_path: Path, key: str) -> None:
        """Upload a local file to storage."""
        if self._use_local:
            dest = self._local_path / key
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_path, dest)
            return

        content_type = self._get_content_type(local_path.name)
        self.client.upload_file(
            str(local_path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    def save_upload(self, key: str, content: bytes) -> None:
        """Save uploaded content directly (for local storage mode)."""
        if not self._use_local:
            raise RuntimeError("save_upload only available in local storage mode")
        dest = self._local_path / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)

    def delete_file(self, key: str) -> None:
        """Delete a file from storage."""
        if self._use_local:
            (self._local_path / key).unlink(missing_ok=True)
            return

        self.client.delete_object(Bucket=self.bucket, Key=key)

    def _get_content_type(self, filename: str) -> str:
        """Get MIME type for a filename."""
        ext = Path(filename).suffix.lower()
        return {
            ".pdf": "application/pdf",
            ".epub": "application/epub+zip",
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".m4b": "audio/mp4",
        }.get(ext, "application/octet-stream")


def get_storage_service() -> StorageService:
    """Dependency for getting the storage service."""
    return StorageService()
