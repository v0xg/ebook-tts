"""SQLAlchemy ORM models for the API database."""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class JobStatus(str, enum.Enum):
    """Status of a conversion job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def utcnow() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """Refresh token for JWT authentication."""

    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")


class Job(Base):
    """Conversion job model."""

    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, index=True)

    # Input file info
    input_filename = Column(String(255), nullable=False)
    input_s3_key = Column(String(512), nullable=False)
    input_format = Column(String(10))  # pdf, epub

    # Conversion settings
    voice = Column(String(50), default="af_heart")
    speed = Column(Float, default=1.0)
    output_format = Column(String(10), default="mp3")  # wav, mp3, m4b
    chapters_to_convert = Column(Text)  # JSON list or null for all

    # Progress tracking
    stage = Column(String(50))
    progress_percent = Column(Float, default=0)
    current_chunk = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    message = Column(Text)

    # Output info
    output_s3_key = Column(String(512))
    duration_seconds = Column(Float)
    chapters_count = Column(Integer)

    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Error info
    error_message = Column(Text)

    # Relationships
    user = relationship("User", back_populates="jobs")
