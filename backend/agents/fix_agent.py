import uuid
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.agents.base import BaseAgent, Tool
from backend.db.models import FailureResult, ChaosSession, SessionStatus, Report


class FixAgent(BaseAgent):
    """
    The most technically impressive agent.
    Takes unhandled failures and generates actual, usable error handling code.
    Not generic advice — specific code patches for the exact gaps found.
    """
    name = "fix"
    system_prompt = """You are the Fix Agent in a chaos engineering system.
You generate specific, production-ready error handling code for identified gaps.

Rules:
- Generate actual code, not advice
- Match the framework (FastAPI, Express, Django, etc.) detected in discovery
- Each fix must be copy-paste ready
- Include the before (broken) and after (fixed) code
- Add comments explaining WHY this fix handles the specific failure

For FastAPI/Python, use patterns like:
- httpx.TimeoutException handling with retry logic
- try/except blocks with specific exception types
- HTTPException with appropriate status codes
- Dependency injection for circuit breakers

Return JSON:
{
  "fixes": [
    {
      "finding_title": "Database errors leak internal details",
      "failure_modes": ["db_connection_drop", "db_timeout"],
      "affected_endpoints": ["/users"],
      "severity": "CRITICAL",
      "explanation": "Why this is dangerous and what the fix does",
      "code_before": "# vulnerable code example",
      "code_after": "# fixed code with proper error handling",
      "language": "python",
      "fix_type": "exception_handler | middleware | decorator | circuit_breaker"
    }
  ],
  "global_fixes": [
    {
      "title": "Add global exception handler",
      "code": "# middleware/handler code",
      "explanation": "Apply this globally to catch all unhandled exceptions"
    }
  ]
}"""

    def __init__(self, db: AsyncSession, session_id: str, framework: str = "fastapi"):
        super().__init__(db, session_id)
        self.framework = framework

    async def handle(self, analysis: dict, failure_results: list[dict]) -> dict:
        await self._update_session_status(SessionStatus.FIXING)

        critical_findings = analysis.get("critical_findings", [])
        all_findings = analysis.get("all_findings", [])

        # Generate fixes for each finding
        fixes_result = await self.run(
            task=f"""Generate production-ready error handling code fixes for these findings.

Framework: {self.framework}
Risk Score: {analysis.get('risk_score', 'unknown')}

Critical findings requiring fixes:
{self._format_findings(critical_findings)}

All findings:
{self._format_findings(all_findings[:8])}

Patterns identified:
{chr(10).join(analysis.get('patterns', []))}

Generate specific, copy-paste ready code fixes for each finding.
Prioritise the CRITICAL and HIGH severity findings first.""",
            context={
                "framework": self.framework,
                "risk_score": analysis.get("risk_score"),
                "findings_count": len(critical_findings) + len(all_findings),
            }
        )

        # Update FailureResult records with fix code
        fixes = fixes_result.get("fixes", [])
        await self._attach_fixes_to_results(fixes, failure_results)

        # Build and save final report
        report = await self._save_report(analysis, fixes_result)

        logger.info(f"[Fix] Generated {len(fixes)} fixes. Report: {report.id}")
        return {
            "report_id": report.id,
            "fixes_count": len(fixes),
            "fixes": fixes,
            "global_fixes": fixes_result.get("global_fixes", []),
        }

    async def _attach_fixes_to_results(self, fixes: list[dict], failure_results: list[dict]):
        """Link fix code to the specific FailureResult records."""
        for fix in fixes:
            affected_modes = fix.get("failure_modes", [])
            affected_paths = fix.get("affected_endpoints", [])

            for result in failure_results:
                if (result["failure_mode"] in affected_modes and
                        result["endpoint_path"] in affected_paths):
                    db_result = await self.db.get(FailureResult, result["id"])
                    if db_result:
                        db_result.fix_generated = True
                        db_result.fix_code = fix.get("code_after", "")
                        db_result.fix_explanation = fix.get("explanation", "")
                        await self.db.flush()

    async def _save_report(self, analysis: dict, fixes_result: dict) -> Report:
        session = await self.db.get(ChaosSession, self.session_id)

        fixes = fixes_result.get("fixes", [])
        fix_count = len(fixes)

        if session:
            session.fixes_generated = fix_count
            session.status = SessionStatus.COMPLETE
            from datetime import datetime
            session.completed_at = datetime.utcnow()
            await self.db.flush()

        report = Report(
            id=str(uuid.uuid4()),
            session_id=self.session_id,
            summary=analysis.get("summary", ""),
            critical_findings=analysis.get("critical_findings", []),
            all_findings=analysis.get("all_findings", []),
            fixes=fixes + fixes_result.get("global_fixes", []),
            risk_score=analysis.get("risk_score", 0),
        )
        self.db.add(report)
        await self.db.flush()

        from backend.core.websocket_manager import ws_manager
        await ws_manager.emit_report_ready(self.session_id, report.id)

        return report

    def _format_findings(self, findings: list[dict]) -> str:
        if not findings:
            return "None"
        lines = []
        for f in findings:
            lines.append(
                f"- [{f.get('severity', 'UNKNOWN')}] {f.get('title', 'Unnamed finding')}\n"
                f"  Endpoints: {f.get('affected_endpoints', [])}\n"
                f"  Failure modes: {f.get('failure_modes', [])}"
            )
        return "\n".join(lines)

    async def _update_session_status(self, status: SessionStatus):
        session = await self.db.get(ChaosSession, self.session_id)
        if session:
            session.status = status
            await self.db.flush()
