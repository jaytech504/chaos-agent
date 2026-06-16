import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional
import json

from backend.db.session import get_db, AsyncSessionLocal
from backend.db.models import ChaosSession, SessionStatus, FailureResult, Endpoint, PullRequest, User
from backend.agents.orchestrator import ChaosOrchestrator
from backend.agents.discovery_agent import DiscoveryAgent
from backend.auth.dependencies import get_current_user, get_optional_user

router = APIRouter()


# ── Input models ──────────────────────────────────────────────────────────────

class ManualEndpoint(BaseModel):
    path: str
    method: str
    description: str = ""
    payload: dict = None


class StartFromSpecUrl(BaseModel):
    """Method 1 — OpenAPI spec URL"""
    target_url: str
    spec_url: str
    target_name: str = "My API"
    github_repo: Optional[str] = None


class StartFromManual(BaseModel):
    """Method 4 — manual endpoint list"""
    target_url: str
    target_name: str = "My API"
    endpoints: list[ManualEndpoint]
    github_repo: Optional[str] = None


# ── Method 1: OpenAPI spec URL ─────────────────────────────────────────────────

@router.post("/from-spec-url")
async def start_from_spec_url(
    body: StartFromSpecUrl,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Start a chaos session using an OpenAPI spec URL.

    Examples:
      FastAPI auto-generates:  http://localhost:8001/openapi.json
      Django with drf-spectacular: https://api.myapp.com/api/schema/
      Spring Boot:  https://api.myapp.com/v3/api-docs
      Express with swagger-jsdoc:  https://api.myapp.com/api-docs
    """
    session_id = str(uuid.uuid4())

    # Fetch and parse spec immediately so we can return errors to the user
    discovery = DiscoveryAgent(db, session_id)
    try:
        endpoints = await discovery.from_openapi_url(body.spec_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not endpoints:
        raise HTTPException(status_code=400,
                            detail="No endpoints found in the spec. Check the URL.")

    # Resolve GitHub token: user's OAuth token > global fallback
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

    background_tasks.add_task(
        _run_pipeline_with_endpoints,
        session_id, body.target_url, endpoints, body.github_repo, github_token
    )

    return {
        "session_id": session_id,
        "method": "openapi_url",
        "endpoints_found": len(endpoints),
        "spec_url": body.spec_url,
        "github_repo": body.github_repo,
    }


# ── Method 2: OpenAPI file upload ──────────────────────────────────────────────

@router.post("/from-spec-file")
async def start_from_spec_file(
    background_tasks: BackgroundTasks,
    target_url: str = Form(...),
    target_name: str = Form("My API"),
    github_repo: Optional[str] = Form(None),
    spec_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Start a chaos session by uploading an OpenAPI spec file.
    Accepts: openapi.json, swagger.json, openapi.yaml, swagger.yaml
    """
    content = await spec_file.read()
    content_str = content.decode("utf-8")

    session_id = str(uuid.uuid4())
    discovery = DiscoveryAgent(db, session_id)

    try:
        endpoints = await discovery.from_openapi_content(content_str)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not endpoints:
        raise HTTPException(status_code=400,
                            detail="No endpoints found in uploaded spec.")

    github_token = _resolve_github_token(user, github_repo)

    session = ChaosSession(
        id=session_id,
        target_url=target_url,
        target_name=target_name,
        github_repo=github_repo,
        user_id=user.id if user else None,
        status=SessionStatus.PENDING,
    )
    db.add(session)
    await db.commit()

    background_tasks.add_task(
        _run_pipeline_with_endpoints,
        session_id, target_url, endpoints, github_repo, github_token
    )

    return {
        "session_id": session_id,
        "method": "openapi_file",
        "endpoints_found": len(endpoints),
        "filename": spec_file.filename,
    }


# ── Method 3: Postman Collection upload ────────────────────────────────────────

@router.post("/from-postman")
async def start_from_postman(
    background_tasks: BackgroundTasks,
    target_url: str = Form(...),
    target_name: str = Form("My API"),
    github_repo: Optional[str] = Form(None),
    collection_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Start a chaos session from a Postman Collection export.
    Export from Postman: Collection → ··· → Export → Collection v2.1
    """
    content = await collection_file.read()
    try:
        collection_data = json.loads(content.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400,
                            detail="Invalid JSON. Export as Collection v2.1 from Postman.")

    session_id = str(uuid.uuid4())
    discovery = DiscoveryAgent(db, session_id)

    try:
        endpoints = await discovery.from_postman_collection(collection_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not endpoints:
        raise HTTPException(status_code=400,
                            detail="No requests found in Postman Collection.")

    github_token = _resolve_github_token(user, github_repo)

    session = ChaosSession(
        id=session_id,
        target_url=target_url,
        target_name=target_name,
        github_repo=github_repo,
        user_id=user.id if user else None,
        status=SessionStatus.PENDING,
    )
    db.add(session)
    await db.commit()

    background_tasks.add_task(
        _run_pipeline_with_endpoints,
        session_id, target_url, endpoints, github_repo, github_token
    )

    return {
        "session_id": session_id,
        "method": "postman_collection",
        "endpoints_found": len(endpoints),
        "collection": collection_data.get("info", {}).get("name", ""),
    }


# ── Method 4: Manual endpoint entry ───────────────────────────────────────────

@router.post("/from-manual")
async def start_from_manual(
    body: StartFromManual,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Start a chaos session with manually entered endpoints.
    Useful when no spec is available and for targeting specific endpoints.
    """
    if not body.endpoints:
        raise HTTPException(status_code=400, detail="No endpoints provided.")

    session_id = str(uuid.uuid4())
    discovery = DiscoveryAgent(db, session_id)

    endpoints = await discovery.from_manual_endpoints(
        [ep.model_dump() for ep in body.endpoints]
    )

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

    background_tasks.add_task(
        _run_pipeline_with_endpoints,
        session_id, body.target_url, endpoints, body.github_repo, github_token
    )

    return {
        "session_id": session_id,
        "method": "manual",
        "endpoints_found": len(endpoints),
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

    endpoints = endpoints_result.scalars().all()
    failures = failures_result.scalars().all()
    prs = prs_result.scalars().all()

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
                "pr_number": pr.pr_number, "pr_url": pr.pr_url,
                "pr_title": pr.pr_title, "finding_title": pr.finding_title,
                "files_changed": pr.files_changed, "status": pr.status,
            }
            for pr in prs
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
