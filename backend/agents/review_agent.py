import os
import shutil
import tempfile
from pathlib import Path
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent, Tool
from backend.core.config import get_settings

settings = get_settings()


class ReviewAgent(BaseAgent):
    """
    Senior-developer code reviewer that validates generated fixes
    before they are committed to a PR.

    Reviews each fix in the context of the ENTIRE file where it will be applied,
    checking for correctness, completeness, and production-readiness.

    Returns either "validated" (fix is good) or "revision_needed" with
    specific feedback to send back to the FixAgent.
    """

    name = "review"
    system_prompt = """You are a SENIOR SOFTWARE ENGINEER performing a rigorous code review.

You are reviewing auto-generated error-handling fixes before they are committed to a production codebase. The codebase could be in any language or framework.

Your job is to review EACH proposed fix in the context of the FULL source file and determine whether it is correct, complete, and production-ready.

## Review Checklist — check EVERY item:

1. **SYMBOL RESOLUTION** — Go through every identifier in code_after (function calls, variable references, method calls, class instantiations). For each one, verify it exists by checking:
   - Is it defined or assigned somewhere in the FULL FILE?
   - Is it a language builtin or standard library symbol?
   - Is it imported at the top of the file?
   - Is it listed in imports_needed?
   - Does using an import require additional setup (e.g. importing a module is not the same as creating an instance — `import logging` does not give you a `logger` variable)?
   If ANY symbol is referenced but cannot be resolved → verdict MUST be "revision_needed".

2. **COMPLETENESS** — The fix must be fully self-contained. If code_after references helper functions, caching mechanisms, utility methods, or configuration variables, those MUST already exist in the file. If they don't, the fix is incomplete.

3. **SYNTAX & STRUCTURE** — The fix must be syntactically valid in the file's language. Indentation, brackets, and nesting must match the surrounding code.

4. **LOGICAL CORRECTNESS** — Trace through the control flow. Check for:
   - Dead code or unreachable branches
   - Variables assigned inside conditional blocks but used outside them
   - Return values that never get used
   - Early returns that skip necessary cleanup
   - Truthiness checks that fail on legitimate zero/empty values

5. **DROP-IN COMPATIBILITY** — The fix must have the same function signature, decorators, and indentation level as the original code. It must not break callers.

6. **INFORMATION SAFETY** — Error responses must never expose internal details (stack traces, connection strings, internal paths, raw exception messages).

7. **CONSISTENCY** — The fix should follow the conventions, patterns, and style already present in the file. If the file uses a particular error handling pattern, logging library, or naming convention, the fix should match.

8. **EDGE CASES** — Consider boundary conditions: null/None/undefined values, zero, empty collections, missing dictionary keys, type mismatches, concurrent access.

For EACH fix, respond with ONE of:
- "validated" — The fix passes all checks and is ready to commit.
- "revision_needed" — The fix has issues. List every issue found and provide specific instructions for how to correct them.

Return JSON:
{
  "verdict": "validated" | "revision_needed",
  "issues": ["specific issue descriptions"],
  "revision_instructions": "Detailed, actionable instructions for correction. Only present if revision_needed."
}"""

    def __init__(
        self,
        db: AsyncSession,
        session_id: str,
        repo_url: str = None,
        github_token: str = None,
    ):
        super().__init__(db, session_id)
        self.repo_url = repo_url
        self.repo_slug = self._parse_repo_slug(repo_url) if repo_url else None
        self._github_token = github_token or settings.github_token
        self._temp_dir = None
        self._repo_path = None

    async def handle(self, fix_result: dict) -> dict:
        """
        Review all fixes. Returns the fix_result dict with fixes updated:
        - Validated fixes pass through unchanged
        - Fixes needing revision are tagged with review feedback

        Returns:
            dict with same structure as fix_result, plus:
            - Each fix gets "review_status": "validated" | "revision_needed"
            - Fixes needing revision get "review_feedback": str
        """
        fixes = fix_result.get("fixes", [])
        if not fixes:
            logger.info("[Review] No fixes to review")
            return fix_result

        # Clone repo to read full file context
        cloned = False
        if self.repo_url and self._github_token:
            try:
                self._clone_repo()
                cloned = True
            except Exception as e:
                logger.error(f"[Review] Failed to clone repo: {e}")

        reviewed_fixes = []
        needs_revision = []

        for i, fix in enumerate(fixes):
            file_path = fix.get("file_path")
            code_before = fix.get("code_before", "")
            code_after = fix.get("code_after", "")
            imports_needed = fix.get("imports_needed", [])
            endpoints = fix.get("affected_endpoints", [])

            endpoint_label = ", ".join(endpoints) if endpoints else "unknown"
            await self._log(
                "thought",
                f"Reviewing fix {i+1}/{len(fixes)}: {fix.get('finding_title', 'unnamed')} "
                f"({endpoint_label})"
            )

            # Read the full file for context
            file_content = ""
            if cloned and file_path:
                file_content = self._read_file(file_path)

            if not file_content:
                # Can't do a file-context review without the file — auto-approve
                logger.warning(f"[Review] Cannot read {file_path} — auto-validating fix")
                fix["review_status"] = "validated"
                reviewed_fixes.append(fix)
                continue

            # Ask the LLM to review the fix in context of the full file
            review_result = await self.run(
                task=f"""Review this proposed code fix. You are looking at the COMPLETE file where the fix will be applied.

## Fix Details
- **Finding:** {fix.get('finding_title', 'Unknown')}
- **Severity:** {fix.get('severity', 'UNKNOWN')}
- **Endpoint(s):** {endpoint_label}
- **File:** {file_path}
- **Lines:** {fix.get('start_line', '?')}-{fix.get('end_line', '?')}

## Proposed imports to add
{imports_needed if imports_needed else "(none)"}

## Original Code (to be replaced)
```
{code_before}
```

## Proposed Fix (replacement)
```
{code_after}
```

## FULL FILE CONTENT (for context)
```
{file_content}
```

Review the proposed fix against the FULL FILE above. Perform your review checklist systematically:

1. **Symbol Resolution**: Go through code_after line by line. For every identifier (function call, variable, method, class), search the full file for where it is defined, imported, or assigned. If any symbol cannot be resolved, the fix is incomplete — reject it and list every unresolved symbol. Remember that importing a module is not the same as creating an instance or variable from it.

2. **Completeness**: Does the fix reference any functions, classes, or variables that don't exist in the file? If so, the fix is incomplete.

3. **Logic Trace**: Trace through each code path. Are there branches that can never execute? Variables that could be undefined when referenced? Truthiness checks that fail on valid edge-case values like zero or empty string?

4. **Drop-in Fit**: Does the replacement have the same function signature, decorators, and indentation as the original?

5. **Information Safety**: Do any error responses leak internal details?

6. **Style Consistency**: Does the fix follow the conventions already used in this file?

Return your verdict as JSON:
{{
  "verdict": "validated" | "revision_needed",
  "issues": ["list of specific issues found, or empty if validated"],
  "revision_instructions": "Detailed instructions for what to change. Only if revision_needed."
}}""",
                context={
                    "file_path": file_path,
                    "finding_title": fix.get("finding_title"),
                }
            )

            verdict = review_result.get("verdict", "validated").lower()
            issues = review_result.get("issues", [])

            if verdict == "revision_needed" and issues:
                logger.info(
                    f"[Review] Fix for {endpoint_label} NEEDS REVISION: "
                    f"{'; '.join(issues)}"
                )
                await self._log(
                    "result",
                    f"❌ Revision needed for {endpoint_label}: {'; '.join(issues)}"
                )
                fix["review_status"] = "revision_needed"
                fix["review_feedback"] = review_result.get(
                    "revision_instructions",
                    "; ".join(issues)
                )
                fix["review_issues"] = issues
                needs_revision.append(fix)
            else:
                logger.info(f"[Review] Fix for {endpoint_label} VALIDATED ✓")
                await self._log("result", f"✅ Validated fix for {endpoint_label}")
                fix["review_status"] = "validated"
                reviewed_fixes.append(fix)

        # Cleanup clone
        self._cleanup()

        # Return updated fix_result
        fix_result["fixes"] = reviewed_fixes
        fix_result["needs_revision"] = needs_revision
        fix_result["review_stats"] = {
            "total": len(fixes),
            "validated": len(reviewed_fixes),
            "revision_needed": len(needs_revision),
        }

        logger.info(
            f"[Review] Done: {len(reviewed_fixes)} validated, "
            f"{len(needs_revision)} need revision"
        )

        return fix_result

    # ── File reading helpers ──────────────────────────────────────────────────

    def _read_file(self, relative_path: str) -> str:
        """Read a file from the cloned repo. Returns content or empty string."""
        try:
            full_path = Path(self._repo_path) / relative_path
            if not full_path.exists():
                logger.warning(f"[Review] File not found: {relative_path}")
                return ""
            content = full_path.read_text(encoding="utf-8")
            # Add line numbers for LLM context
            numbered = "\n".join(
                f"{i+1:4d} | {line}"
                for i, line in enumerate(content.splitlines())
            )
            return numbered
        except Exception as e:
            logger.error(f"[Review] Error reading {relative_path}: {e}")
            return ""

    # ── Repo management (shared pattern with FixAgent) ────────────────────────

    def _parse_repo_slug(self, repo_url: str) -> str:
        url = repo_url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        if "github.com/" in url:
            return url.split("github.com/")[-1]
        return url

    def _clone_repo(self):
        import git
        self._temp_dir = tempfile.mkdtemp(prefix="chaos_agent_review_")
        self._repo_path = os.path.join(self._temp_dir, "repo")

        # Determine if token looks like a placeholder
        token = self._github_token
        is_placeholder = (
            not token or
            "token" in token.lower() or
            "placeholder" in token.lower() or
            token == "mock_token"
        )

        if is_placeholder:
            clone_url = f"https://github.com/{self.repo_slug}.git"
            logger.info(f"[Review] Token looks like placeholder. Cloning public repo {self.repo_slug} without token...")
        else:
            clone_url = f"https://{token}@github.com/{self.repo_slug}.git"
            logger.info(f"[Review] Cloning {self.repo_slug} for review with token...")

        try:
            git.Repo.clone_from(clone_url, self._repo_path, depth=1)
        except Exception as e:
            if not is_placeholder:
                logger.warning(f"[Review] Failed to clone with token: {e}. Retrying without token...")
                clone_url = f"https://github.com/{self.repo_slug}.git"
                git.Repo.clone_from(clone_url, self._repo_path, depth=1)
            else:
                raise

        logger.info(f"[Review] Cloned to {self._repo_path}")

    def _cleanup(self):
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
