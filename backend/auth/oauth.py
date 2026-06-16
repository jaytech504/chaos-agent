"""
GitHub OAuth flow.

Handles the OAuth dance:
  1. Generate the GitHub authorize URL
  2. Exchange the callback code for an access token
  3. Fetch the GitHub user profile
"""

import httpx
from loguru import logger

from backend.core.config import get_settings

settings = get_settings()

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_REPOS_URL = "https://api.github.com/user/repos"

# Scopes: repo (push branches + open PRs), read:user (profile info)
OAUTH_SCOPES = "repo read:user user:email"


def get_github_login_url(state: str = "") -> str:
    """Build the URL to redirect the user to GitHub for authorization."""
    params = {
        "client_id": settings.github_client_id,
        "scope": OAUTH_SCOPES,
        "redirect_uri": f"{settings.frontend_url}/auth/callback",
    }
    if state:
        params["state"] = state
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GITHUB_AUTHORIZE_URL}?{query}"


async def exchange_code_for_token(code: str) -> str:
    """Exchange the OAuth callback code for a GitHub access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()

    if "error" in data:
        logger.error(f"[OAuth] GitHub token exchange failed: {data}")
        raise ValueError(data.get("error_description", data["error"]))

    return data["access_token"]


async def fetch_github_user(access_token: str) -> dict:
    """Fetch the authenticated user's GitHub profile."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()


async def fetch_user_repos(
    access_token: str,
    page: int = 1,
    per_page: int = 30,
    sort: str = "updated",
) -> list[dict]:
    """
    Fetch repositories the authenticated user has access to.
    Returns a simplified list with only the fields the frontend needs.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GITHUB_REPOS_URL,
            params={
                "page": page,
                "per_page": per_page,
                "sort": sort,
                "affiliation": "owner,collaborator,organization_member",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=15.0,
        )
        response.raise_for_status()
        repos = response.json()

    return [
        {
            "id": repo["id"],
            "full_name": repo["full_name"],       # owner/repo
            "name": repo["name"],
            "private": repo["private"],
            "description": repo.get("description", ""),
            "html_url": repo["html_url"],
            "default_branch": repo.get("default_branch", "main"),
            "language": repo.get("language"),
            "updated_at": repo.get("updated_at"),
            "permissions": repo.get("permissions", {}),
        }
        for repo in repos
    ]
