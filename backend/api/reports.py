from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.session import get_db
from backend.db.models import Report, FailureResult

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
                "endpoint": f.endpoint_id,
                "fix_code": f.fix_code,
                "fix_explanation": f.fix_explanation,
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
