from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent, Tool
from backend.db.models import ChaosSession, SessionStatus, FailureResult, FailureStatus
from sqlalchemy import select


class AnalystAgent(BaseAgent):
    """
    Analyses all failure results and identifies:
    - Patterns across failures (e.g. all DB failures unhandled)
    - Most critical gaps
    - Risk scoring
    """
    name = "analyst"
    system_prompt = """You are the Analyst Agent in a chaos engineering system.
You receive a list of failure injection results and must produce a structured analysis.

Your job:
1. Identify which failure modes are consistently unhandled
2. Find patterns (e.g. all database failures crash the app)
3. Prioritise findings by severity
4. Calculate an overall risk score (0-100, higher = more dangerous)

Severity levels:
- CRITICAL: error details / stack traces leaked to users (security risk)
- HIGH: app returns 500 with no useful error message
- MEDIUM: app degrades but doesn't crash
- LOW: app handles gracefully but could improve

Return JSON:
{
  "risk_score": 75,
  "critical_findings": [
    {
      "title": "Database errors leak internal details",
      "severity": "CRITICAL",
      "affected_endpoints": ["/users", "/orders"],
      "failure_modes": ["db_connection_drop"],
      "evidence": "Response body contains SQLAlchemy traceback"
    }
  ],
  "all_findings": [...],
  "patterns": ["All POST endpoints vulnerable to malformed JSON", "No timeout handling on any endpoint"],
  "summary": "The application has significant gaps in error handling..."
}"""

    def __init__(self, db: AsyncSession, session_id: str):
        super().__init__(db, session_id)

    async def handle(self, failure_results: list[dict]) -> dict:
        await self._update_session_status(SessionStatus.ANALYSING)

        # Group results for analysis
        unhandled = [r for r in failure_results if r["result"] == "unhandled"]
        handled = [r for r in failure_results if r["result"] == "handled"]
        degraded = [r for r in failure_results if r["result"] == "degraded"]
        leaked = [r for r in failure_results if r.get("error_leaked")]

        analysis = await self.run(
            task=f"""Analyse these chaos engineering results:

Total failures injected: {len(failure_results)}
Unhandled (app crashed/leaked): {len(unhandled)}
Handled gracefully: {len(handled)}
Degraded (partial handling): {len(degraded)}
Error details leaked to users: {len(leaked)}

Unhandled results:
{self._format_results(unhandled[:20])}

Leaked errors:
{self._format_results(leaked[:10])}

Produce a comprehensive risk analysis with specific findings and patterns.""",
            context={
                "total": len(failure_results),
                "unhandled_count": len(unhandled),
                "leaked_count": len(leaked),
            }
        )

        logger.info(f"[Analyst] Risk score: {analysis.get('risk_score', 'N/A')}")
        return analysis

    def _format_results(self, results: list[dict]) -> str:
        if not results:
            return "None"
        lines = []
        for r in results:
            lines.append(
                f"- {r['endpoint_path']} | {r['failure_mode']} | "
                f"status={r.get('status_code')} | leaked={r.get('error_leaked')}"
            )
        return "\n".join(lines)

    async def _update_session_status(self, status: SessionStatus):
        session = await self.db.get(ChaosSession, self.session_id)
        if session:
            session.status = status
            await self.db.flush()
