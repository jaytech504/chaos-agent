from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.session import get_db
from backend.db.models import Report, FailureResult, Endpoint

router = APIRouter()


@router.get("/{report_id}")
async def get_report(report_id: str, db: AsyncSession = Depends(get_db)):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Get all failure results with fixes
    failures_result = await db.execute(
        select(FailureResult)
        .where(FailureResult.session_id == report.session_id)
        .where(FailureResult.fix_generated == True)
    )
    fixed_failures = failures_result.scalars().all()

    # Load all endpoints for the session to map endpoint_id -> path
    endpoints_result = await db.execute(
        select(Endpoint).where(Endpoint.session_id == report.session_id)
    )
    endpoints_map = {ep.id: ep for ep in endpoints_result.scalars().all()}

    # Map (failure_mode, endpoint_id) -> code_before
    before_code_map = {}
    for fix in (report.fixes or []):
        modes = fix.get("failure_modes", [])
        endpoints = fix.get("affected_endpoints", [])
        code_before = fix.get("code_before", "")
        for mode in modes:
            for ep_path in endpoints:
                # Find endpoint_id for this path
                for ep_id, ep_obj in endpoints_map.items():
                    if ep_obj.path == ep_path:
                        before_code_map[(mode, ep_id)] = code_before

    return {
        "id": report.id,
        "session_id": report.session_id,
        "risk_score": report.risk_score,
        "summary": report.summary,
        "critical_findings": report.critical_findings,
        "all_findings": report.all_findings,
        "fixes": report.fixes,
        "fixed_failures": [
            {
                "failure_mode": f.failure_mode,
                "endpoint": endpoints_map[f.endpoint_id].path if f.endpoint_id in endpoints_map else f.endpoint_id,
                "fix_code": f.fix_code,
                "fix_explanation": f.fix_explanation,
                "before_code": before_code_map.get((f.failure_mode, f.endpoint_id), ""),
            }
            for f in fixed_failures
        ],
        "created_at": report.created_at.isoformat(),
    }


@router.get("/session/{session_id}")
async def get_report_by_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Report).where(Report.session_id == session_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found for this session")
    return {"report_id": report.id}
