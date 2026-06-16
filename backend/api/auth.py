"""
Auth API routes.

Handles GitHub OAuth login flow and user-related endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from backend.db.session import get_db
from backend.db.models import User
from backend.auth.oauth import (
    get_github_login_url,
    exchange_code_for_token,
    fetch_github_user,
    fetch_user_repos,
)
from backend.auth.dependencies import (
    create_jwt,
    upsert_user,
    get_current_user,
)

router = APIRouter()


# ── OAuth flow ────────────────────────────────────────────────────────────────

@router.get("/github/login")
async def github_login():
    """
    Returns the GitHub OAuth authorization URL.
    The frontend redirects the user to this URL.
    """
    url = get_github_login_url()
    return {"url": url}


@router.get("/github/callback")
@router.post("/github/callback")
async def github_callback(
    code: str = Query(..., description="OAuth code from GitHub redirect"),
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the frontend after GitHub redirects back with a code.
    Exchanges the code for an access token, fetches the user profile,
    creates/updates the user in DB, and returns a JWT.
    """
    try:
        # Exchange code for GitHub access token
        access_token = await exchange_code_for_token(code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"GitHub auth failed: {e}")
    except Exception as e:
        logger.error(f"[Auth] Token exchange error: {e}")
        raise HTTPException(status_code=500, detail="Failed to authenticate with GitHub")

    try:
        # Fetch user profile from GitHub
        gh_user = await fetch_github_user(access_token)
    except Exception as e:
        logger.error(f"[Auth] User fetch error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch GitHub profile")

    # Upsert user in DB
    user = await upsert_user(
        db=db,
        github_id=gh_user["id"],
        github_username=gh_user["login"],
        github_avatar_url=gh_user.get("avatar_url", ""),
        email=gh_user.get("email", ""),
        access_token=access_token,
    )

    # Create JWT for the frontend
    token = create_jwt(user.id, user.github_username)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "github_username": user.github_username,
            "github_avatar_url": user.github_avatar_url,
            "email": user.email,
        },
    }


# ── User info ─────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return {
        "id": user.id,
        "github_username": user.github_username,
        "github_avatar_url": user.github_avatar_url,
        "email": user.email,
        "created_at": user.created_at.isoformat(),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


# ── Repo listing ──────────────────────────────────────────────────────────────

@router.get("/repos")
async def list_repos(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
):
    """
    List GitHub repos the authenticated user has access to.
    Uses the user's OAuth token so they only see repos they can push to.
    """
    try:
        repos = await fetch_user_repos(
            access_token=user.github_access_token,
            page=page,
            per_page=per_page,
        )
        return {"repos": repos, "page": page, "per_page": per_page}
    except Exception as e:
        logger.error(f"[Auth] Repo list error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch repos from GitHub")
