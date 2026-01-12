"""FastAPI dependency injection functions."""

from typing import Generator

from fastapi import Cookie, Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .db.database import SessionLocal
from .db.models import User

security = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """
    Dependency that validates JWT and returns the current user.

    Raises HTTPException 401 if token is invalid or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception from None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    """
    Optional authentication - returns user if valid token, None otherwise.

    Useful for endpoints that work with or without authentication.
    """
    if credentials is None:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            return None

        user = db.query(User).filter(User.id == user_id).first()
        if user and user.is_active:
            return user

    except JWTError:
        pass

    return None


def get_current_user_flexible(
    token: str | None = Query(None, description="JWT token for SSE clients"),
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """
    Flexible authentication for SSE endpoints.

    Accepts JWT from multiple sources (for EventSource compatibility):
    - Query param: ?token=<jwt>
    - Cookie: access_token=<jwt>
    - Header: Authorization: Bearer <jwt>
    """
    # Try to extract token from available sources
    jwt_token = token or access_token
    if not jwt_token and authorization and authorization.startswith("Bearer "):
        jwt_token = authorization.split(" ", 1)[1]

    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            jwt_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception from None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user
