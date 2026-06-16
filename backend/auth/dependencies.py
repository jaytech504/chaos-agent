"""
FastAPI auth dependencies.

Provides `get_current_user` and `get_optional_user` for protecting routes.
Uses JWT tokens issued after GitHub OAuth login.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from backend.core.config import get_settings
from backend.db.session import get_db
from backend.db.models import User

settings = get_settings()

# HTTPBearer extracts "Bearer <token>" from the Authorization header
_bearer_scheme = HTTPBearer(auto_error=False)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_jwt(user_id: str, github_username: str) -> str:
    """Create a signed JWT for a logged-in user."""
    payload = {
        "sub": user_id,
        "github_username": github_username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str) -> dict:
    """Decode and verify a JWT. Raises on invalid/expired tokens."""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired — please log in again",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# ── User upsert ──────────────────────────────────────────────────────────────

async def upsert_user(
    db: AsyncSession,
    github_id: int,
    github_username: str,
    github_avatar_url: str,
    email: str,
    access_token: str,
) -> User:
    """
    Create or update a user after GitHub OAuth login.
    Updates the access token and last_login on every login.
    """
    result = await db.execute(
        select(User).where(User.github_id == github_id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Returning user — update token and login time
        user.github_access_token = access_token
        user.github_username = github_username
        user.github_avatar_url = github_avatar_url
        user.email = email
        user.last_login_at = datetime.utcnow()
        logger.info(f"[Auth] Returning user: {github_username} (id={user.id})")
    else:
        # New user
        user = User(
            id=str(uuid.uuid4()),
            github_id=github_id,
            github_username=github_username,
            github_avatar_url=github_avatar_url,
            github_access_token=access_token,
            email=email,
        )
        db.add(user)
        logger.info(f"[Auth] New user created: {github_username} (id={user.id})")

    await db.flush()
    return user


# ── FastAPI dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Require a valid JWT and return the User.
    Use this on protected endpoints.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — please log in with GitHub",
        )

    payload = decode_jwt(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found — please log in again",
        )

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Try to extract the user from JWT, but return None if no token is present.
    Use this on endpoints that work both authenticated and unauthenticated.
    """
    if not credentials:
        return None

    try:
        payload = decode_jwt(credentials.credentials)
        user_id = payload.get("sub")
        if user_id:
            return await db.get(User, user_id)
    except HTTPException:
        pass

    return None
