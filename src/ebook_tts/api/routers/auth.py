"""Authentication router for user registration, login, and token management."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..db.models import User
from ..dependencies import get_current_user, get_db
from ..models.user import (
    TokenRefresh,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from ..services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user account.

    - **email**: Valid email address (must be unique)
    - **password**: Password (minimum 8 characters)
    """
    auth_service = AuthService(db)
    return auth_service.register(user_data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get tokens",
)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate with email and password to receive JWT tokens.

    Returns:
    - **access_token**: Short-lived token for API requests (30 min default)
    - **refresh_token**: Long-lived token for getting new access tokens (7 days default)
    """
    auth_service = AuthService(db)
    return auth_service.login(credentials)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    """
    Get a new access token using a valid refresh token.

    The old refresh token is invalidated (token rotation).
    """
    auth_service = AuthService(db)
    return auth_service.refresh(token_data.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and invalidate refresh token",
)
def logout(
    token_data: TokenRefresh,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Invalidate the refresh token to logout.

    Requires authentication.
    """
    auth_service = AuthService(db)
    auth_service.logout(token_data.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user info",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Get information about the currently authenticated user."""
    return UserResponse.model_validate(current_user)
