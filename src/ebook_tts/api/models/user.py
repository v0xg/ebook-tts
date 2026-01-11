"""Pydantic models for user authentication."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Request model for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Request model for user login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response model for authentication tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class TokenRefresh(BaseModel):
    """Request model for token refresh."""

    refresh_token: str


class UserResponse(BaseModel):
    """Response model for user information."""

    id: str
    email: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True
