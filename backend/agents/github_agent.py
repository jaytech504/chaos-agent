import os
import uuid
import shutil
import tempfile
from pathlib import Path
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent, Tool
from backend.core.config import get_settings
from backend.core.websocket_manager import ws_manager
from backend.db.models import PullRequest

settings = get_settings()


class GitHubAgent(BaseAgent):
    """
    Takes the Fix Agent's output and makes it real.

    For each critical/high finding:
    1. Clones the target repo to a temp directory
    2. Asks Qwen to locate the exact file and line that needs the fix
    3. Applies the fix code to the correct location
    4. Creates a new branch
    5. Commits the change with a descriptive message
    6. Opens a GitHub Pull Request

    The PR description includes:
    - What failure mode was found
    - What the app was doing wrong
    - What the fix does and why
    - Link back to the chaos session report
    """

    name = "github"
    system_prompt = """You are the GitHub Agent in a chaos engineering system.
You receive a code fix and must locate exactly where in the source code to apply it.

Your job:
1. Find the correct source file for the affected endpoint
2. Find the exact function/route handler that needs the fix
3. Determine the precise insertion point (line number or after which code)
4. Apply the fix cleanly without breaking surrounding code

When analysing source files:
- Look for route decorators (@app.get, @router.post, @app.route, etc.)
- Match the endpoint path from the finding to the decorator
- Find the function body that handles that route
- Identify where the try/except block or error handler should be inserted

Return JSON:
{
  "file_path": "relative/path/to/file.py",
  "target_function": "function_name",
  "insertion_strategy": "wrap_body | add_middleware | add_import | replace_function",
  "original_code": "the exact code block to replace",
  "fixed_code": "the replacement code with the fix applied",
  "imports_needed": ["from sqlalchemy.exc import SQLAlchemyError"],
  "confidence": 0.0-1.0,
  "reasoning": "Why this is the correct location"
}"""

    def __init__(self, db: AsyncSession, session_id: str, repo_url: str, github_token: str = None):
        super().__init__(db, session_id)
        self.repo_url = repo_url                        # e.g. https://github.com/jason/myapp
        self.repo_slug = self._parse_repo_slug(repo_url)  # e.g. jason/myapp
        self._github_token = github_token or settings.github_token
        self._temp_dir = None
        self._repo_path = None
        self._github = None
        self._gh_repo = None
        self._register_tools()

    def _parse_repo_slug(self, repo_url: str) -> str:
        """Extract owner/repo from any GitHub URL format."""
        url = repo_url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        if "github.com/" in url:
            return url.split("github.com/")[-1]
        return url

    def _register_tools(self):
        self.register_tool(Tool(
            name="read_source_file",
            description="Read a source file from the cloned repository",
            parameters={
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path relative to repo root, e.g. 'app/main.py'"
                    }
                },
                "required": ["relative_path"],
            },
            func=self._read_source_file,
        ))

        self.register_tool(Tool(
            name="list_source_files",
            description="List all Python/JS source files in the repository",
            parameters={
                "type": "object",
                "properties": {
                    "extension": {
                        "type": "string",
                        "description": "File extension to filter by, e.g. '.py' or '.ts'",
                        "default": ".py"
                    }
                },
            },
            func=self._list_source_files,
        ))

        self.register_tool(Tool(
            name="search_in_files",
            description="Search for a string across all source files",
            parameters={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "String to search for, e.g. '@app.get(\"/users\"'"
                    }
                },
                "required": ["search_term"],
            },
            func=self._search_in_files,
        ))

    # ── File Tools ────────────────────────────────────────────────────────────

    async def _read_source_file(self, relative_path: str) -> dict:
        try:
            full_path = Path(self._repo_path) / relative_path
            if not full_path.exists():
                return {"error": f"File not found: {relative_path}"}
            content = full_path.read_text(encoding="utf-8")
            # Return with line numbers so Qwen can reference them
            numbered = "\n".join(
                f"{i+1:4d} | {line}"
                for i, line in enumerate(content.splitlines())
            )
            return {"path": relative_path, "content": numbered, "lines": len(content.splitlines())}
        except Exception as e:
            return {"error": str(e)}

    async def _list_source_files(self, extension: str = ".py") -> dict:
        try:
            repo_path = Path(self._repo_path)
            files = [
                str(f.relative_to(repo_path))
                for f in repo_path.rglob(f"*{extension}")
                if ".git" not in str(f) and "node_modules" not in str(f)
                and "__pycache__" not in str(f) and "venv" not in str(f)
            ]
            return {"files": files[:50]}
        except Exception as e:
            return {"error": str(e)}

    async def _search_in_files(self, search_term: str) -> dict:
        try:
            results = []
            repo_path = Path(self._repo_path)
            for f in repo_path.rglob("*.py"):
                if ".git" in str(f) or "__pycache__" in str(f):
                    continue
                try:
                    content = f.read_text(encoding="utf-8")
                    if search_term in content:
                        lines = content.splitlines()
                        matches = [
                            {"line": i + 1, "content": line.strip()}
                            for i, line in enumerate(lines)
                            if search_term in line
                        ]
                        results.append({
                            "file": str(f.relative_to(repo_path)),
                            "matches": matches,
                        })
                except Exception:
                    continue
            return {"results": results}
        except Exception as e:
            return {"error": str(e)}

    # ── Core GitHub Operations ────────────────────────────────────────────────

    def _setup_github(self):
        """Initialize PyGithub client."""
        from github import Github
        if not self._github_token:
            raise ValueError("No GitHub token available — cannot open PRs")
        self._github = Github(self._github_token)
        self._gh_repo = self._github.get_repo(self.repo_slug)
        logger.info(f"[GitHub] Connected to repo: {self.repo_slug}")

    def _clone_repo(self):
        """Clone the repo to a temp directory."""
        import git
        self._temp_dir = tempfile.mkdtemp(prefix="chaos_agent_")
        self._repo_path = os.path.join(self._temp_dir, "repo")

        # Build authenticated clone URL
        clone_url = f"https://{self._github_token}@github.com/{self.repo_slug}.git"
        logger.info(f"[GitHub] Cloning {self.repo_slug}...")
        git.Repo.clone_from(clone_url, self._repo_path, depth=1)
        logger.info(f"[GitHub] Cloned to {self._repo_path}")

    def _cleanup(self):
        """Remove temp directory."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _apply_fix_to_file(self, file_path: str, original_code: str, fixed_code: str,
                            imports_needed: list[str],
                            start_line: int | None = None,
                            end_line: int | None = None) -> bool:
        """Apply the fix by replacing the original code block with fixed code.

        Strategy:
        1. Try exact string replacement first.
        2. If that fails but start_line/end_line are provided, replace those lines directly.
        3. If neither works, skip (do not append junk comments).
        """
        full_path = Path(self._repo_path) / file_path
        if not full_path.exists():
            logger.error(f"[GitHub] File not found: {file_path}")
            return False

        content = full_path.read_text(encoding="utf-8")

        # Add missing imports at top of file
        if imports_needed:
            import_block = "\n".join(imports_needed)
            if import_block not in content:
                lines = content.splitlines()
                last_import_line = 0
                for i, line in enumerate(lines):
                    if line.startswith("import ") or line.startswith("from "):
                        last_import_line = i
                lines.insert(last_import_line + 1, import_block)
                content = "\n".join(lines)

        # Strategy 1: Exact string replacement
        if original_code and original_code in content:
            content = content.replace(original_code, fixed_code, 1)
            full_path.write_text(content, encoding="utf-8")
            logger.info(f"[GitHub] Fix applied via string match to {file_path}")
            return True

        # Strategy 2: Line-range replacement
        if start_line and end_line:
            lines = content.splitlines()
            if 1 <= start_line <= end_line <= len(lines):
                # Replace lines [start_line-1 : end_line] (0-indexed) with the fixed code
                fixed_lines = fixed_code.splitlines()
                lines[start_line - 1 : end_line] = fixed_lines
                content = "\n".join(lines)
                full_path.write_text(content, encoding="utf-8")
                logger.info(f"[GitHub] Fix applied via line-range ({start_line}-{end_line}) to {file_path}")
                return True
            else:
                logger.warning(f"[GitHub] Line range {start_line}-{end_line} out of bounds for {file_path} ({len(lines)} lines)")

        # No strategy worked — skip this fix
        logger.warning(f"[GitHub] Could not apply fix to {file_path} — neither string match nor line-range succeeded")
        return False

    def _create_branch_and_pr(
        self,
        branch_name: str,
        files_changed: list[str],
        pr_title: str,
        pr_body: str,
        commit_message: str,
    ) -> dict:
        """Commit changes to a new branch and open a PR."""
        import git

        repo = git.Repo(self._repo_path)

        # Create and checkout new branch
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()

        # Stage all changes
        repo.index.add(files_changed)

        # Commit
        repo.index.commit(
            commit_message,
            author=git.Actor("Chaos Agent", "chaos-agent@noreply.github.com"),
        )

        # Push branch
        origin = repo.remote("origin")
        origin.push(refspec=f"{branch_name}:{branch_name}")
        logger.info(f"[GitHub] Pushed branch: {branch_name}")

        # Open PR via GitHub API
        default_branch = self._gh_repo.default_branch
        pr = self._gh_repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=branch_name,
            base=default_branch,
        )

        logger.info(f"[GitHub] PR opened: #{pr.number} — {pr.html_url}")
        return {"pr_number": pr.number, "pr_url": pr.html_url}

    def _build_consolidated_pr_body(self, fixes_applied: list[dict], session_id: str) -> str:
        """Build a PR body summarizing all applied fixes."""
        sections = []
        for fix in fixes_applied:
            endpoints = ", ".join(fix.get("affected_endpoints", ["unknown"]))
            sections.append(f"""### {fix.get('finding_title', 'Error handling fix')}
**Severity:** {fix.get('severity', 'HIGH')}
**Endpoints:** {endpoints}
**File:** `{fix.get('file_path', 'unknown')}`

{fix.get('explanation', 'Adds proper error handling for identified failure modes.')}
""")

        body = f"""## 🤖 Auto-generated by Chaos Agent

This PR consolidates **{len(fixes_applied)}** error-handling fix(es) identified during chaos testing.

{chr(10).join(sections)}

---
*Generated by [Chaos Agent](https://github.com) | Session: `{session_id}`*
*Review carefully before merging — automated fixes should always be human-verified.*"""
        return body

    # ── Main Entry Point ──────────────────────────────────────────────────────

    async def handle(self, fixes_result: dict, analysis: dict, report_id: str) -> list[dict]:
        """
        Apply all fixes to a single clone and open ONE consolidated PR.
        Returns list of opened PR records (typically one).
        """
        if not self._github_token:
            logger.warning("[GitHub] No GitHub token available — skipping PR creation")
            await ws_manager.emit_status(
                self.session_id, "github_skipped",
                "No GitHub token configured — fixes generated in report only"
            )
            return []

        await ws_manager.emit_status(
            self.session_id, "opening_prs",
            f"Opening Pull Request on {self.repo_slug}..."
        )

        try:
            self._setup_github()
            self._clone_repo()
        except Exception as e:
            logger.error(f"[GitHub] Setup failed: {e}")
            await ws_manager.emit_status(self.session_id, "github_failed", str(e))
            return []

        fixes = fixes_result.get("fixes", [])
        if not fixes:
            logger.warning("[GitHub] No fixes to apply")
            self._cleanup()
            return []

        # Apply all fixes to the single clone
        applied_fixes = []
        files_changed = set()

        # Sort fixes by file_path then start_line descending so that
        # line-range replacements don't shift line numbers for later fixes in the same file
        sorted_fixes = sorted(
            fixes,
            key=lambda f: (f.get("file_path", ""), -(f.get("start_line", 0) or 0))
        )

        for fix in sorted_fixes:
            file_path = fix.get("file_path")
            original_code = fix.get("code_before", fix.get("original_code", ""))
            fixed_code = fix.get("code_after", fix.get("fixed_code", ""))
            imports_needed = fix.get("imports_needed", [])
            start_line = fix.get("start_line")
            end_line = fix.get("end_line")

            if not file_path:
                logger.warning(f"[GitHub] Fix missing file_path, skipping: {fix.get('finding_title')}")
                continue

            if not fixed_code:
                logger.warning(f"[GitHub] Fix has no code_after, skipping: {fix.get('finding_title')}")
                continue

            await self._log("thought",
                            f"Applying fix to {file_path} "
                            f"(lines {start_line}-{end_line}) for: "
                            f"{', '.join(fix.get('affected_endpoints', []))}")

            success = self._apply_fix_to_file(
                file_path, original_code, fixed_code, imports_needed,
                start_line=start_line, end_line=end_line
            )

            if success:
                applied_fixes.append(fix)
                files_changed.add(file_path)
                logger.info(f"[GitHub] ✓ Applied fix for {fix.get('finding_title')} to {file_path}")
            else:
                logger.warning(f"[GitHub] ✗ Failed to apply fix for {fix.get('finding_title')} to {file_path}")

        if not applied_fixes:
            logger.warning("[GitHub] No fixes could be applied")
            self._cleanup()
            await ws_manager.emit_status(self.session_id, "github_failed",
                                         "No fixes could be applied to the codebase")
            return []

        # Build ONE consolidated branch + PR
        branch_name = f"chaos-agent/fixes-{self.session_id[:8]}"
        pr_title = f"fix: {len(applied_fixes)} error-handling improvements from chaos testing"
        pr_body = self._build_consolidated_pr_body(applied_fixes, self.session_id)
        commit_msg = (f"fix: {len(applied_fixes)} error-handling improvements\n\n"
                      f"Auto-generated by Chaos Agent\n"
                      f"Session: {self.session_id}")

        try:
            pr_info = self._create_branch_and_pr(
                branch_name=branch_name,
                files_changed=list(files_changed),
                pr_title=pr_title,
                pr_body=pr_body,
                commit_message=commit_msg,
            )
        except Exception as e:
            logger.error(f"[GitHub] Failed to create PR: {e}")
            self._cleanup()
            await ws_manager.emit_status(self.session_id, "github_failed", str(e))
            return []

        # Save to DB
        pr_record = PullRequest(
            id=str(uuid.uuid4()),
            session_id=self.session_id,
            report_id=report_id,
            github_repo=self.repo_slug,
            branch_name=branch_name,
            pr_number=pr_info.get("pr_number"),
            pr_url=pr_info.get("pr_url"),
            pr_title=pr_title,
            finding_title=f"{len(applied_fixes)} fixes consolidated",
            files_changed=list(files_changed),
            status="opened",
        )
        self.db.add(pr_record)
        await self.db.flush()

        # Stream PR opened event to frontend
        await ws_manager.broadcast(self.session_id, "pr_opened", {
            "pr_number": pr_info.get("pr_number"),
            "pr_url": pr_info.get("pr_url"),
            "pr_title": pr_title,
            "fixes_count": len(applied_fixes),
            "files_changed": list(files_changed),
        })

        self._cleanup()

        logger.info(f"[GitHub] Opened 1 consolidated PR with {len(applied_fixes)} fixes")
        await ws_manager.emit_status(
            self.session_id, "prs_complete",
            f"Pull Request opened on {self.repo_slug} with {len(applied_fixes)} fix(es)"
        )

        return [{
            "pr_number": pr_info.get("pr_number"),
            "pr_url": pr_info.get("pr_url"),
            "pr_title": pr_title,
            "files_changed": list(files_changed),
            "fixes_applied": len(applied_fixes),
        }]

