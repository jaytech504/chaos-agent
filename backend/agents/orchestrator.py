from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.chaos_agent import ChaosAgent
from backend.agents.analyst_agent import AnalystAgent
from backend.agents.fix_agent import FixAgent
from backend.agents.review_agent import ReviewAgent
from backend.agents.github_agent import GitHubAgent
from backend.core.websocket_manager import ws_manager
from backend.core.config import get_settings
from backend.db.models import ChaosSession, SessionStatus

settings = get_settings()


class ChaosOrchestrator:
    """
    Coordinates the pipeline after discovery is complete:
    Chaos Injection → Analysis → Fix Generation → Review → GitHub PRs

    Discovery happens before the orchestrator runs —
    in the API layer via the DiscoveryAgent.
    """

    def __init__(self, db: AsyncSession, session_id: str):
        self.db = db
        self.session_id = session_id

    async def run_from_endpoints(
        self,
        target_url: str,
        endpoints: list[dict],
        github_repo: str = None,
        github_token: str = None,
    ) -> dict:
        logger.info(
            f"[Orchestrator] Starting with {len(endpoints)} endpoints "
            f"for {target_url}"
        )

        try:
            # ── Stage 1: Chaos Injection ──────────────────────────────────────
            await ws_manager.emit_status(
                self.session_id, "injecting",
                f"Injecting failures into {len(endpoints)} endpoints..."
            )
            chaos = ChaosAgent(self.db, self.session_id, target_url)
            failure_results = await chaos.handle(endpoints)
            await chaos.close()

            unhandled = [r for r in failure_results if r["result"] == "unhandled"]
            logger.info(
                f"[Orchestrator] {len(failure_results)} injected, "
                f"{len(unhandled)} unhandled"
            )

            session = await self.db.get(ChaosSession, self.session_id)
            if session:
                session.unhandled_count = len(unhandled)
                await self.db.flush()

            # ── Stage 2: Analysis ─────────────────────────────────────────────
            await ws_manager.emit_status(
                self.session_id, "analysing",
                "Analysing failure patterns..."
            )
            analyst = AnalystAgent(self.db, self.session_id)
            analysis = await analyst.handle(failure_results)

            # ── Stage 3: Fix Generation ───────────────────────────────────────
            await ws_manager.emit_status(
                self.session_id, "fixing",
                "Generating error handling code..."
            )
            # Resolve token: per-user OAuth token > global fallback
            effective_token = github_token or settings.github_token
            fixer = FixAgent(
                self.db, self.session_id,
                repo_url=github_repo,
                github_token=effective_token
            )
            fix_result = await fixer.handle(analysis, failure_results)

            # ── Stage 3.5: Fix Review ─────────────────────────────────────────
            # ReviewAgent validates each fix like a senior developer.
            # If fixes need revision, they go back to FixAgent for correction.
            if github_repo and effective_token:
                await ws_manager.emit_status(
                    self.session_id, "reviewing",
                    "Senior code review of generated fixes..."
                )
                reviewer = ReviewAgent(
                    self.db, self.session_id,
                    repo_url=github_repo,
                    github_token=effective_token,
                )

                max_review_rounds = 2
                for review_round in range(max_review_rounds):
                    fix_result = await reviewer.handle(fix_result)

                    needs_revision = fix_result.get("needs_revision", [])
                    if not needs_revision:
                        # All fixes validated — proceed
                        logger.info(
                            f"[Orchestrator] Review round {review_round + 1}: "
                            f"all fixes validated ✓"
                        )
                        break

                    logger.info(
                        f"[Orchestrator] Review round {review_round + 1}: "
                        f"{len(needs_revision)} fix(es) need revision"
                    )
                    await ws_manager.emit_status(
                        self.session_id, "fixing",
                        f"Revising {len(needs_revision)} fix(es) based on review feedback..."
                    )

                    # Send rejected fixes back to FixAgent for revision
                    revised_fixer = FixAgent(
                        self.db, self.session_id,
                        repo_url=github_repo,
                        github_token=effective_token
                    )
                    revised_fixes = await revised_fixer.revise_fixes(needs_revision)

                    # Merge revised fixes back into the result
                    fix_result["fixes"] = fix_result.get("fixes", []) + revised_fixes
                    fix_result["fixes_count"] = len(fix_result["fixes"])

                    # Clear the needs_revision list for the next review round
                    fix_result.pop("needs_revision", None)

                    await ws_manager.emit_status(
                        self.session_id, "reviewing",
                        f"Re-reviewing revised fixes (round {review_round + 2})..."
                    )
                else:
                    # Max rounds reached — include remaining unrevised fixes as-is
                    remaining = fix_result.pop("needs_revision", [])
                    if remaining:
                        logger.warning(
                            f"[Orchestrator] Max review rounds reached. "
                            f"{len(remaining)} fix(es) included without full validation."
                        )
                        fix_result["fixes"] = fix_result.get("fixes", []) + remaining
                        fix_result["fixes_count"] = len(fix_result["fixes"])

                review_stats = fix_result.get("review_stats", {})
                logger.info(
                    f"[Orchestrator] Review complete: "
                    f"{review_stats.get('validated', 0)} validated, "
                    f"{review_stats.get('revision_needed', 0)} revised"
                )

            # ── Stage 4: GitHub PRs ───────────────────────────────────────────
            prs_opened = []
            if github_repo and effective_token:
                await ws_manager.emit_status(
                    self.session_id, "opening_prs",
                    f"Opening Pull Requests on {github_repo}..."
                )
                github = GitHubAgent(
                    self.db, self.session_id, github_repo,
                    github_token=effective_token,
                )
                prs_opened = await github.handle(
                    fixes_result=fix_result,
                    analysis=analysis,
                    report_id=fix_result.get("report_id"),
                )
            elif github_repo and not effective_token:
                await ws_manager.emit_status(
                    self.session_id, "github_skipped",
                    "No GitHub token available — log in with GitHub or set GITHUB_TOKEN"
                )

            await ws_manager.emit_status(
                self.session_id, "complete",
                f"Done. Risk score: {analysis.get('risk_score', 0)}/100 | "
                f"{len(prs_opened)} PR(s) opened"
            )

            return {
                "session_id": self.session_id,
                "report_id": fix_result.get("report_id"),
                "endpoints_tested": len(endpoints),
                "failures_injected": len(failure_results),
                "unhandled_count": len(unhandled),
                "fixes_generated": fix_result.get("fixes_count", 0),
                "risk_score": analysis.get("risk_score", 0),
                "prs_opened": len(prs_opened),
            }

        except Exception as e:
            logger.error(f"[Orchestrator] Pipeline failed: {e}")
            session = await self.db.get(ChaosSession, self.session_id)
            if session:
                session.status = SessionStatus.FAILED
                await self.db.flush()
            await ws_manager.emit_status(self.session_id, "failed", str(e))
            raise
