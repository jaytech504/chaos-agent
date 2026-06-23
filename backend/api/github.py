from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from loguru import logger

from backend.db.session import get_db
from backend.db.models import PullRequest, User
from backend.auth.dependencies import get_optional_user
from backend.core.websocket_manager import ws_manager

router = APIRouter()


@router.get("")
async def list_pull_requests(
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(PullRequest).order_by(PullRequest.created_at.desc())
    if session_id:
        query = query.where(PullRequest.session_id == session_id)
    result = await db.execute(query.limit(50))
    prs = result.scalars().all()
    return [
        {
            "id": pr.id,
            "session_id": pr.session_id,
            "github_repo": pr.github_repo,
            "pr_number": pr.pr_number,
            "pr_url": pr.pr_url,
            "pr_title": pr.pr_title,
            "finding_title": pr.finding_title,
            "files_changed": pr.files_changed,
            "status": pr.status,
            "created_at": pr.created_at.isoformat(),
        }
        for pr in prs
    ]


@router.get("/{pr_id}")
async def get_pull_request(pr_id: str, db: AsyncSession = Depends(get_db)):
    pr = await db.get(PullRequest, pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    return {
        "id": pr.id,
        "session_id": pr.session_id,
        "report_id": pr.report_id,
        "github_repo": pr.github_repo,
        "branch_name": pr.branch_name,
        "pr_number": pr.pr_number,
        "pr_url": pr.pr_url,
        "pr_title": pr.pr_title,
        "finding_title": pr.finding_title,
        "files_changed": pr.files_changed,
        "status": pr.status,
        "created_at": pr.created_at.isoformat(),
    }


@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Receives GitHub webhook events for PR state changes.
    Add in GitHub repo: Settings → Webhooks → your-server/api/github/webhook
    """
    payload = await request.json()

    if x_github_event != "pull_request":
        return {"ok": True, "ignored": True}

    action = payload.get("action")
    pr_data = payload.get("pull_request", {})
    pr_number = pr_data.get("number")
    repo_full_name = payload.get("repository", {}).get("full_name")
    merged = pr_data.get("merged", False)

    logger.info(f"[Webhook] PR #{pr_number} {action} on {repo_full_name}")

    result = await db.execute(
        select(PullRequest)
        .where(PullRequest.pr_number == pr_number)
        .where(PullRequest.github_repo == repo_full_name)
    )
    pr_record = result.scalar_one_or_none()
    if not pr_record:
        return {"ok": True, "message": "PR not tracked"}

    if action == "closed" and merged:
        pr_record.status = "merged"
    elif action == "closed":
        pr_record.status = "closed"
    elif action == "reopened":
        pr_record.status = "opened"
    else:
        return {"ok": True}

    await db.commit()

    await ws_manager.broadcast(pr_record.session_id, "pr_status_updated", {
        "pr_number": pr_number,
        "status": pr_record.status,
        "merged": merged,
        "finding_title": pr_record.finding_title,
    })

    return {"ok": True, "status": pr_record.status}


@router.post("/{pr_id}/sync")
async def sync_pr_status(pr_id: str, db: AsyncSession = Depends(get_db)):
    """Manually sync one PR's status from GitHub API."""
    from backend.core.config import get_settings
    settings = get_settings()

    if not settings.github_token:
        raise HTTPException(status_code=400, detail="No GitHub token configured")

    pr_record = await db.get(PullRequest, pr_id)
    if not pr_record:
        raise HTTPException(status_code=404, detail="PR not found")

    try:
        from github import Github
        gh = Github(settings.github_token)
        repo = gh.get_repo(pr_record.github_repo)
        gh_pr = repo.get_pull(pr_record.pr_number)

        if gh_pr.merged:
            pr_record.status = "merged"
        elif gh_pr.state == "closed":
            pr_record.status = "closed"
        else:
            pr_record.status = "opened"

        await db.commit()
        return {"pr_number": pr_record.pr_number, "status": pr_record.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pr_id}/merge")
async def merge_pull_request(
    pr_id: str,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Merge the specified pull request on GitHub and update its status.
    """
    pr_record = await db.get(PullRequest, pr_id)
    if not pr_record:
        raise HTTPException(status_code=404, detail="PR not found")

    # Resolve token: user's OAuth token > global fallback
    from backend.core.config import get_settings
    settings = get_settings()
    token = None
    if user and user.github_access_token:
        token = user.github_access_token
    else:
        token = settings.github_token or None

    if not token:
        raise HTTPException(status_code=400, detail="No GitHub token available. Please log in with GitHub.")

    try:
        from github import Github
        gh = Github(token)
        repo = gh.get_repo(pr_record.github_repo)
        gh_pr = repo.get_pull(pr_record.pr_number)

        # Merge the PR
        merge_status = gh_pr.merge(
            commit_message="🤖 Auto-merged by Chaos Agent",
            merge_method="merge"
        )

        if merge_status.merged:
            pr_record.status = "merged"
            await db.commit()

            # Broadcast the merge status update
            await ws_manager.broadcast(pr_record.session_id, "pr_status_updated", {
                "pr_number": pr_record.pr_number,
                "status": "merged",
                "merged": True,
                "finding_title": pr_record.finding_title,
            })
            return {"ok": True, "status": "merged", "message": merge_status.message}
        else:
            raise HTTPException(status_code=500, detail=f"Merge failed: {merge_status.message}")

    except Exception as e:
        logger.error(f"[GitHub API] Merge error for PR {pr_record.pr_number}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

