"""Authentication service for JWT and password handling."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db.models import RefreshToken, User
from ..models.user import TokenResponse, UserCreate, UserLogin, UserResponse

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service for user authentication and JWT token management."""

    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()

    def register(self, user_data: UserCreate) -> UserResponse:
        """
        Register a new user account.

        Raises HTTPException 400 if email already exists.
        """
        existing = self.db.query(User).filter(User.email == user_data.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        user = User(
            id=str(uuid.uuid4()),
            email=user_data.email,
            hashed_password=pwd_context.hash(user_data.password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return UserResponse.model_validate(user)

    def login(self, credentials: UserLogin) -> TokenResponse:
        """
        Authenticate user and return JWT tokens.

        Raises HTTPException 401 if credentials are invalid.
        """
        user = self.db.query(User).filter(User.email == credentials.email).first()

        if not user or not pwd_context.verify(credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )

        return self._create_tokens(user)

    def refresh(self, refresh_token: str) -> TokenResponse:
        """
        Refresh access token using a valid refresh token.

        Raises HTTPException 401 if refresh token is invalid or expired.
        """
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        stored_token = (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == token_hash,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )

        if not stored_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user = stored_token.user

        # Delete old refresh token (rotation)
        self.db.delete(stored_token)
        self.db.commit()

        return self._create_tokens(user)

    def logout(self, refresh_token: str) -> None:
        """Invalidate a refresh token."""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).delete()
        self.db.commit()

    def _create_tokens(self, user: User) -> TokenResponse:
        """Create access and refresh tokens for a user."""
        # Access token
        access_expires = timedelta(minutes=self.settings.access_token_expire_minutes)
        access_token = self._create_jwt(
            data={"sub": user.id, "type": "access"},
            expires_delta=access_expires,
        )

        # Refresh token (random UUID, stored as hash)
        refresh_token = str(uuid.uuid4())
        refresh_expires = datetime.now(timezone.utc) + timedelta(
            days=self.settings.refresh_token_expire_days
        )

        stored_refresh = RefreshToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
            expires_at=refresh_expires,
        )
        self.db.add(stored_refresh)
        self.db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(access_expires.total_seconds()),
        )

    def _create_jwt(self, data: dict, expires_delta: timedelta) -> str:
        """Create a JWT token with the given data and expiration."""
        to_encode = data.copy()
        to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
        return jwt.encode(
            to_encode,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )
