"""Configuration management using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="EBOOK_TTS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "ebook-tts-api"
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./data/ebook_tts.db"

    # JWT Authentication
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION"  # Required in production
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # S3-compatible storage (Cloudflare R2, Backblaze B2, etc.)
    s3_endpoint_url: str = ""  # e.g., https://xxx.r2.cloudflarestorage.com
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = "ebook-tts"
    s3_region: str = "auto"  # Use "auto" for Cloudflare R2

    # Upload/download limits
    max_upload_size_mb: int = 100
    upload_url_expire_seconds: int = 3600  # 1 hour
    download_url_expire_seconds: int = 86400  # 24 hours

    # Worker settings
    max_concurrent_jobs: int = 1  # Limited RAM on free tier
    job_timeout_seconds: int = 3600  # 1 hour max per job
    cleanup_after_days: int = 7  # Delete old jobs/files after this many days

    # TTS settings
    tts_device: str = "cuda"  # Use GPU locally; set to "cpu" for Fly.io
    default_voice: str = "af_heart"
    default_chunk_size: int = 2000

    # Local storage (for testing without S3)
    use_local_storage: bool = False  # Set to True for local dev without S3
    local_storage_path: str = "./data/uploads"

    @property
    def s3_configured(self) -> bool:
        """Check if S3 storage is configured."""
        return bool(
            self.s3_endpoint_url
            and self.s3_access_key_id
            and self.s3_secret_access_key
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
