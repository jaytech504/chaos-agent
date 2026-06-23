import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete
from typing import Optional
import json
from loguru import logger

from backend.db.session import get_db, AsyncSessionLocal
from backend.db.models import ChaosSession, SessionStatus, FailureResult, Endpoint, PullRequest, User, AgentStep
from backend.agents.orchestrator import ChaosOrchestrator
from backend.agents.discovery_agent import DiscoveryAgent
from backend.auth.dependencies import get_current_user, get_optional_user

router = APIRouter()


from backend.core.draft_cache import draft_cache

# ── Input models ──────────────────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    draft_id: str
    target_url: str
    target_name: str = "My API"
    github_repo: Optional[str] = None
    selected_temp_ids: list[str]


class StartSessionLegacyRequest(BaseModel):
    target_url: str
    target_name: str = "My API"
    github_repo: Optional[str] = None


# ── Legacy/Direct Start Session ────────────────────────────────────────────────

@router.post("")
async def start_session_legacy(
    body: StartSessionLegacyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Directly start a chaos session by auto-discovering endpoints from {target_url}/openapi.json.
    """
    session_id = str(uuid.uuid4())

    # 1. Create and persist session first to satisfy foreign key constraints
    session = ChaosSession(
        id=session_id,
        target_url=body.target_url,
        target_name=body.target_name,
        github_repo=body.github_repo,
        user_id=user.id if user else None,
        status=SessionStatus.PENDING,
    )
    db.add(session)
    await db.commit()
    
    # 2. Run discovery
    spec_url = f"{body.target_url.rstrip('/')}/openapi.json"
    logger.info(f"[Sessions] Legacy direct start. Scanning spec URL: {spec_url}")
    
    discovery = DiscoveryAgent(db, session_id)
    try:
        endpoints = await discovery.from_openapi_url(spec_url)
    except Exception as e:
        logger.error(f"[Sessions] Discovery failed for {spec_url}: {e}")
        # Clean up session since it failed
        await db.delete(session)
        await db.commit()
        raise HTTPException(status_code=400, detail=f"Failed to discover endpoints from {spec_url}: {e}")

    if not endpoints:
        # Clean up session
        await db.delete(session)
        await db.commit()
        raise HTTPException(status_code=400, detail="No endpoints found in spec.")

    # 3. Trigger background tasks
    github_token = _resolve_github_token(user, body.github_repo)
    background_tasks.add_task(
        _run_pipeline_with_endpoints,
        session_id, body.target_url, endpoints, body.github_repo, github_token
    )

    return {
        "session_id": session_id,
        "method": "openapi_url",
        "endpoints_found": len(endpoints),
    }


# ── Start Session from Spec Draft ──────────────────────────────────────────────

@router.post("/start")
async def start_session(
    body: StartSessionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Start a chaos session using endpoints selected from a parsed draft.
    """
    if not body.selected_temp_ids:
        raise HTTPException(status_code=400, detail="No endpoints selected.")

    # Retrieve from short-lived TTL cache
    draft = draft_cache.get(body.draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft spec not found or expired.")

    all_draft_endpoints = draft.get("endpoints", [])
    filtered_endpoints = [
        ep for ep in all_draft_endpoints
        if ep.get("temp_id") in body.selected_temp_ids
    ]

    if not filtered_endpoints:
        raise HTTPException(
            status_code=400,
            detail="None of the selected endpoints exist in the draft spec."
        )

    session_id = str(uuid.uuid4())
    github_token = _resolve_github_token(user, body.github_repo)

    session = ChaosSession(
        id=session_id,
        target_url=body.target_url,
        target_name=body.target_name,
        github_repo=body.github_repo,
        user_id=user.id if user else None,
        status=SessionStatus.PENDING,
    )
    db.add(session)
    await db.commit()

    # Persist only the chosen endpoints
    discovery = DiscoveryAgent(db, session_id)
    saved_endpoints = await discovery.save_selected_endpoints(filtered_endpoints)

    # Invalidate cache entry
    draft_cache.delete(body.draft_id)

    background_tasks.add_task(
        _run_pipeline_with_endpoints,
        session_id, body.target_url, saved_endpoints, body.github_repo, github_token
    )

    return {
        "session_id": session_id,
        "method": draft.get("method", "openapi_url"),
        "endpoints_found": len(saved_endpoints),
        "github_repo": body.github_repo,
    }



# ── Session list + detail ──────────────────────────────────────────────────────

@router.get("")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    query = select(ChaosSession).order_by(desc(ChaosSession.created_at)).limit(20)
    # If logged in, only show the user's sessions
    if user:
        query = query.where(ChaosSession.user_id == user.id)
    result = await db.execute(query)
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "target_name": s.target_name,
            "target_url": s.target_url,
            "github_repo": s.github_repo,
            "status": s.status.value,
            "endpoints_found": s.endpoints_found,
            "failures_injected": s.failures_injected,
            "unhandled_count": s.unhandled_count,
            "fixes_generated": s.fixes_generated,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]


@router.get("/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(ChaosSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    endpoints_result = await db.execute(
        select(Endpoint).where(Endpoint.session_id == session_id)
    )
    failures_result = await db.execute(
        select(FailureResult).where(FailureResult.session_id == session_id)
    )
    prs_result = await db.execute(
        select(PullRequest).where(PullRequest.session_id == session_id)
    )
    steps_result = await db.execute(
        select(AgentStep).where(AgentStep.session_id == session_id).order_by(AgentStep.created_at.asc())
    )

    endpoints = endpoints_result.scalars().all()
    failures = failures_result.scalars().all()
    prs = prs_result.scalars().all()
    steps = steps_result.scalars().all()

    return {
        "id": session.id,
        "target_name": session.target_name,
        "target_url": session.target_url,
        "github_repo": session.github_repo,
        "status": session.status.value,
        "endpoints_found": session.endpoints_found,
        "failures_injected": session.failures_injected,
        "unhandled_count": session.unhandled_count,
        "fixes_generated": session.fixes_generated,
        "created_at": session.created_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "endpoints": [
            {
                "id": e.id, "path": e.path, "method": e.method,
                "description": e.description, "dependencies": e.dependencies,
            }
            for e in endpoints
        ],
        "failures": [
            {
                "id": f.id, "endpoint_id": f.endpoint_id,
                "failure_mode": f.failure_mode, "result": f.result.value,
                "status_code": f.status_code_received,
                "error_leaked": f.error_leaked, "fix_generated": f.fix_generated,
            }
            for f in failures
        ],
        "pull_requests": [
            {
                "id": pr.id,
                "pr_number": pr.pr_number,
                "pr_url": pr.pr_url,
                "pr_title": pr.pr_title,
                "finding_title": pr.finding_title,
                "files_changed": pr.files_changed,
                "status": pr.status,
                "branch_name": pr.branch_name,
            }
            for pr in prs
        ],
        "agent_steps": [
            {
                "agent": step.agent,
                "step_type": step.step_type,
                "content": step.content,
                "created_at": step.created_at.isoformat(),
            }
            for step in steps
        ],
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resolve_github_token(user: Optional[User], github_repo: Optional[str]) -> Optional[str]:
    """
    Determine which GitHub token to use for PR creation.
    Priority: user's OAuth token > global fallback from .env
    """
    if not github_repo:
        return None

    if user and user.github_access_token:
        return user.github_access_token

    # Fallback to global token (for dev/demo use)
    from backend.core.config import get_settings
    settings = get_settings()
    return settings.github_token or None


# ── Background pipeline ────────────────────────────────────────────────────────

async def _run_pipeline_with_endpoints(
    session_id: str,
    target_url: str,
    endpoints: list[dict],
    github_repo: str = None,
    github_token: str = None,
):
    """
    Run chaos pipeline starting from pre-discovered endpoints.
    Discovery has already happened — skip straight to chaos injection.
    """
    async with AsyncSessionLocal() as db:
        try:
            orchestrator = ChaosOrchestrator(db, session_id)
            await orchestrator.run_from_endpoints(
                target_url, endpoints, github_repo, github_token
            )
            await db.commit()
        except Exception as e:
            await db.rollback()


# ── Retry failed session ──────────────────────────────────────────────────────

@router.post("/{session_id}/retry")
async def retry_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Rerun a failed chaos session using its pre-discovered endpoints.
    """
    session = await db.get(ChaosSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if user and session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to retry this session")

    # Update status to pending
    session.status = SessionStatus.PENDING
    session.fixes_generated = 0
    session.prs_opened = 0
    session.risk_score = 0
    session.unhandled_count = 0
    session.completed_at = None

    # Clear previous run results
    from backend.db.models import FailureResult, AgentStep, Report, PullRequest
    await db.execute(delete(PullRequest).where(PullRequest.session_id == session_id))
    await db.execute(delete(Report).where(Report.session_id == session_id))
    await db.execute(delete(AgentStep).where(AgentStep.session_id == session_id))
    await db.execute(delete(FailureResult).where(FailureResult.session_id == session_id))

    await db.flush()

    # Load endpoints
    endpoints_result = await db.execute(
        select(Endpoint).where(Endpoint.session_id == session_id)
    )
    endpoints = endpoints_result.scalars().all()
    if not endpoints:
        raise HTTPException(status_code=400, detail="No endpoints found to retry.")

    # Convert endpoints to list of dicts for run_from_endpoints
    endpoints_payload = [
        {
            "id": ep.id,
            "path": ep.path,
            "method": ep.method,
            "description": ep.description,
            "sample_payload": ep.sample_payload,
            "dependencies": ep.dependencies,
        }
        for ep in endpoints
    ]

    github_token = _resolve_github_token(user, session.github_repo)

    # Trigger background pipeline rerun
    background_tasks.add_task(
        _run_pipeline_with_endpoints,
        session_id, session.target_url, endpoints_payload, session.github_repo, github_token
    )

    await db.commit()

    return {"status": "retrying", "session_id": session_id}
