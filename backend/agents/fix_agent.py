import os
import shutil
import tempfile
import uuid
from pathlib import Path
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.agents.base import BaseAgent, Tool
from backend.core.config import get_settings
from backend.db.models import FailureResult, ChaosSession, SessionStatus, Report

settings = get_settings()


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
      "fix_type": "exception_handler | middleware | decorator | circuit_breaker",
      "file_path": "app/main.py",
      "imports_needed": ["from sqlalchemy.exc import SQLAlchemyError"]
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

    def __init__(self, db: AsyncSession, session_id: str, repo_url: str = None, github_token: str = None, framework: str = "fastapi"):
        super().__init__(db, session_id)
        self.framework = framework
        self.repo_url = repo_url
        self.repo_slug = self._parse_repo_slug(repo_url) if repo_url else None
        self._github_token = github_token or settings.github_token
        self._temp_dir = None
        self._repo_path = None
        self.language = "python"
        self.detected_framework = framework

    async def handle(self, analysis: dict, failure_results: list[dict]) -> dict:
        await self._update_session_status(SessionStatus.FIXING)

        critical_findings = analysis.get("critical_findings", [])
        all_findings = analysis.get("all_findings", [])

        # Try to clone repo if provided
        cloned_successfully = False
        if self.repo_url and self._github_token:
            try:
                self._clone_repo()
                self._register_tools()
                cloned_successfully = True
            except Exception as e:
                logger.error(f"[Fix] Failed to clone repo {self.repo_url}: {e}")

        fixes = []
        global_fixes = []

        if cloned_successfully:
            # Process each critical/high finding — split by individual endpoint
            for finding in critical_findings[:5]:
                affected_endpoints = finding.get("affected_endpoints", [])
                if not affected_endpoints:
                    # No specific endpoints — generate a single vacuum fix
                    fallback_fix = await self._generate_vacuum_fix(finding)
                    if fallback_fix:
                        fixes.extend(fallback_fix)
                    continue

                # Process each endpoint individually
                for endpoint_path in affected_endpoints[:5]:
                    try:
                        await self._log("thought", f"Locating endpoint {endpoint_path} for finding: {finding.get('title')}")

                        # Try to find the method for this endpoint path from the DB
                        method = "GET"  # fallback
                        try:
                            from backend.db.models import Endpoint
                            from sqlalchemy import select
                            stmt = select(Endpoint).where(Endpoint.session_id == self.session_id).where(Endpoint.path == endpoint_path)
                            res = await self.db.execute(stmt)
                            ep_record = res.scalar_one_or_none()
                            if ep_record:
                                method = ep_record.method
                        except Exception as db_err:
                            logger.warning(f"[Fix] Failed to lookup method for {endpoint_path}: {db_err}")

                        # Try to locate programmatically first to save tokens
                        location = self._locate_endpoint_programmatically(endpoint_path, method)

                        if location:
                            await self._log(
                                "thought",
                                f"Programmatically located endpoint {endpoint_path} ({method}) in "
                                f"{location['file_path']} (lines {location['start_line']}-{location['end_line']})"
                            )
                        else:
                            await self._log("thought", f"Could not programmatically locate {endpoint_path}. Falling back to LLM locator...")
                            # Step 1: Locate the single endpoint's code block
                            location = await self.run(
                                task=f"""Find the source code for ONE specific endpoint handler.

Endpoint to find: {endpoint_path}
Framework: {self.detected_framework}

Steps:
1. Search for route decorators matching "{endpoint_path}" (e.g. @app.get("{endpoint_path}") or @router.get("{endpoint_path}"))
2. Read the file containing this endpoint
3. Identify the COMPLETE function (decorator + def line + full body until the next decorator or top-level definition)
4. Return the start and end line numbers

IMPORTANT: Return ONLY this single endpoint's function. Do NOT include other endpoints.

Return JSON:
{{
  "file_path": "relative/path/to/file.py",
  "target_function": "function_name",
  "start_line": 42,
  "end_line": 58,
  "original_code": "the exact lines from start_line to end_line, copied character for character",
  "reasoning": "Why this is the correct location"
}}""",
                                context={"endpoint": endpoint_path, "finding_title": finding.get("title")}
                            )

                        file_path = location.get("file_path")
                        original_code = location.get("original_code")
                        start_line = location.get("start_line")
                        end_line = location.get("end_line")

                        if not file_path or not original_code:
                            logger.warning(f"[Fix] Could not locate {endpoint_path}. Skipping.")
                            continue

                        # Step 2: Generate a tailored fix for this single endpoint
                        await self._log("thought", f"Generating fix for {endpoint_path} in {file_path}:{start_line}-{end_line}")
                        lang_rules = self._get_lang_rules()
                        tailored_result = await self.run(
                            task=f"""Generate a production-ready error handling fix for this SINGLE endpoint.

Endpoint: {endpoint_path}
Finding: {finding.get('title')}
Framework: {self.detected_framework}
File: {file_path} (lines {start_line}-{end_line})
Failure modes: {finding.get('failure_modes', [])}

Original Code (lines {start_line}-{end_line}):
{original_code}

Rules:
- Replace ONLY this endpoint's function. Do NOT include other endpoints.
- The code_before MUST be the exact original code above, character for character.
- The code_after must be a drop-in replacement with proper error handling added.
- CRITICAL: Do NOT call any function that does not exist in the file. If you need a helper, define it inline or inside the function.
{lang_rules}
- CRITICAL: Do NOT invent helper functions like `_get_cached()` or `_store_result()`. Inline the logic instead.
- Do NOT add section dividers or comment headers like "# --- Endpoint: ... ---"
- Do NOT include meta-instruction comments like "# At line X, add..." or "# Add to existing import block". These are NOT code.
- Put ALL needed imports in the "imports_needed" array. Do NOT put import statements inside code_after.
- The imports_needed array must contain ONLY actual import lines (e.g. "import logging", "from fastapi import HTTPException"). Do NOT include non-import setup like "logger = logging.getLogger(__name__)" — put those in code_after if needed.

Return JSON:
{{
  "finding_title": "{finding.get('title')}",
  "failure_modes": {finding.get('failure_modes', [])},
  "affected_endpoints": ["{endpoint_path}"],
  "severity": "{finding.get('severity', 'HIGH')}",
  "explanation": "What was wrong and what the fix does",
  "code_before": "exact original code to replace",
  "code_after": "fixed code with proper error handling",
  "language": "{self.language}",
  "fix_type": "exception_handler",
  "imports_needed": ["list of imports/setup lines needed, e.g. packages/modules"]
}}""",
                            context={"endpoint": endpoint_path, "original_code": original_code}
                        )

                        # Ensure metadata is correctly set
                        tailored_result["file_path"] = file_path
                        tailored_result["start_line"] = start_line
                        tailored_result["end_line"] = end_line
                        tailored_result["affected_endpoints"] = [endpoint_path]
                        if not tailored_result.get("code_before"):
                            tailored_result["code_before"] = original_code

                        fixes.append(tailored_result)
                        logger.info(f"[Fix] Generated fix for {endpoint_path} @ {file_path}:{start_line}-{end_line}")

                    except Exception as e:
                        logger.error(f"[Fix] Failed fix for endpoint '{endpoint_path}': {e}")
                        continue

            self._cleanup()
        else:
            # Fallback: vacuum-style generate fixes for all critical findings in one go
            logger.info("[Fix] No repo clone or token, falling back to vacuum-style fix generation.")
            vacuum_result = await self._generate_vacuum_all_fixes(analysis, critical_findings, all_findings)
            fixes = vacuum_result.get("fixes", [])
            global_fixes = vacuum_result.get("global_fixes", [])

        fixes_result = {
            "fixes": fixes,
            "global_fixes": global_fixes
        }

        # Update FailureResult records with fix code
        await self._attach_fixes_to_results(fixes, failure_results)

        # Build and save final report
        report = await self._save_report(analysis, fixes_result)

        logger.info(f"[Fix] Generated {len(fixes)} fixes. Report: {report.id}")
        return {
            "report_id": report.id,
            "fixes_count": len(fixes),
            "fixes": fixes,
            "global_fixes": global_fixes,
        }

    async def revise_fixes(self, fixes_needing_revision: list[dict]) -> list[dict]:
        """
        Re-generate fixes that failed review, using the reviewer's feedback.

        Each fix in the list has:
        - All the original fix fields (code_before, code_after, file_path, etc.)
        - review_feedback: str — specific instructions from the ReviewAgent
        - review_issues: list[str] — list of issues found

        Returns a list of revised fixes.
        """
        if not fixes_needing_revision:
            return []

        # Clone repo to read file context for revision
        cloned = False
        if self.repo_url and self._github_token:
            try:
                self._clone_repo()
                self._register_tools()
                cloned = True
            except Exception as e:
                logger.error(f"[Fix] Failed to clone repo for revision: {e}")

        revised_fixes = []

        for fix in fixes_needing_revision:
            endpoint_label = ", ".join(fix.get("affected_endpoints", ["unknown"]))
            await self._log(
                "thought",
                f"Revising fix for {endpoint_label} based on review feedback"
            )

            # Read the full file for context
            file_content = ""
            if cloned and fix.get("file_path"):
                try:
                    result = await self._read_source_file(fix["file_path"])
                    file_content = result.get("content", "")
                except Exception:
                    pass

            review_feedback = fix.get("review_feedback", "")
            review_issues = fix.get("review_issues", [])

            try:
                lang_rules = self._get_lang_rules()
                revised = await self.run(
                    task=f"""A senior code reviewer has REJECTED your previous fix and provided specific feedback.
You MUST address ALL of the reviewer's issues and generate a corrected fix.

## Original Code (what is currently in the file)
```
{fix.get('code_before', '')}
```

## Your Previous Fix (REJECTED)
```
{fix.get('code_after', '')}
```

## Reviewer's Issues
{chr(10).join(f'- {issue}' for issue in review_issues)}

## Reviewer's Instructions
{review_feedback}

## Full File Context
```
{file_content if file_content else '(file not available)'}
```

## Requirements
- Fix ALL issues identified by the reviewer
- The code_before MUST remain exactly the same (it's the original code to replace)
- The code_after must address every reviewer issue
- CRITICAL: Do NOT call any function that is not defined in the file. If you need a helper function, define it INSIDE the endpoint function or inline the logic.
{lang_rules}
- CRITICAL: Do NOT invent helper functions like `_get_cached()`, `_store_result()` — either define them in the file or inline the logic.
- Make sure all imports are accounted for — either already in the file or in imports_needed
- Do NOT introduce any dead code or unreachable branches
- Match the coding style of the rest of the file

Return JSON:
{{
  "finding_title": "{fix.get('finding_title', '')}",
  "failure_modes": {fix.get('failure_modes', [])},
  "affected_endpoints": {fix.get('affected_endpoints', [])},
  "severity": "{fix.get('severity', 'HIGH')}",
  "explanation": "Updated explanation of what the fix does",
  "code_before": "exact original code (unchanged)",
  "code_after": "corrected fix addressing all reviewer feedback",
  "language": "{self.language}",
  "fix_type": "exception_handler",
  "imports_needed": ["list of ALL imports/setup lines needed by the fix"]
}}""",
                    context={
                        "review_feedback": review_feedback,
                        "original_fix": fix,
                    }
                )

                # Preserve metadata from the original fix
                revised["file_path"] = fix.get("file_path")
                revised["start_line"] = fix.get("start_line")
                revised["end_line"] = fix.get("end_line")
                revised["affected_endpoints"] = fix.get("affected_endpoints", [])

                # Make sure code_before is preserved exactly
                if not revised.get("code_before"):
                    revised["code_before"] = fix.get("code_before", "")

                revised["revision_attempt"] = fix.get("revision_attempt", 0) + 1
                revised_fixes.append(revised)

                logger.info(f"[Fix] Revised fix for {endpoint_label}")
                await self._log("result", f"✅ Revised fix for {endpoint_label}")

            except Exception as e:
                logger.error(f"[Fix] Failed to revise fix for {endpoint_label}: {e}")
                # Keep the original fix as-is if revision fails
                fix["review_status"] = "revision_failed"
                revised_fixes.append(fix)

        if cloned:
            self._cleanup()

        return revised_fixes

    async def _generate_vacuum_fix(self, finding: dict) -> list[dict]:
        """Generate a fallback isolated template fix for a single finding."""
        result = await self.run(
            task=f"""Generate production-ready error handling code fixes for this finding.

Framework: {self.framework}
Finding:
- Severity: {finding.get('severity', 'UNKNOWN')}
- Title: {finding.get('title', 'Unnamed finding')}
- Endpoints: {finding.get('affected_endpoints', [])}
- Failure modes: {finding.get('failure_modes', [])}

Return JSON with a 'fixes' list, matching:
{{
  "fixes": [
    {{
      "finding_title": "{finding.get('title')}",
      "failure_modes": {finding.get('failure_modes', [])},
      "affected_endpoints": {finding.get('affected_endpoints', [])},
      "severity": "{finding.get('severity', 'UNKNOWN')}",
      "explanation": "Why this is dangerous and what the fix does",
      "code_before": "# vulnerable code example",
      "code_after": "# fixed code with proper error handling",
      "language": "python",
      "fix_type": "exception_handler"
    }}
  ]
}}""",
            context={"finding": finding}
        )
        return result.get("fixes", [])

    async def _generate_vacuum_all_fixes(self, analysis: dict, critical_findings: list[dict], all_findings: list[dict]) -> dict:
        """Existing implementation of FixAgent running in a vacuum."""
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
        return fixes_result

    def _parse_repo_slug(self, repo_url: str) -> str:
        """Extract owner/repo from any GitHub URL format."""
        url = repo_url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        if "github.com/" in url:
            return url.split("github.com/")[-1]
        return url

    def _clone_repo(self):
        """Clone the repo to a temp directory."""
        import git
        self._temp_dir = tempfile.mkdtemp(prefix="chaos_agent_fix_")
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
            logger.info(f"[Fix] Token looks like placeholder. Cloning public repo {self.repo_slug} without token...")
        else:
            clone_url = f"https://{token}@github.com/{self.repo_slug}.git"
            logger.info(f"[Fix] Cloning {self.repo_slug} with token...")

        try:
            git.Repo.clone_from(clone_url, self._repo_path, depth=1)
        except Exception as e:
            if not is_placeholder:
                logger.warning(f"[Fix] Failed to clone with token: {e}. Retrying without token...")
                clone_url = f"https://github.com/{self.repo_slug}.git"
                git.Repo.clone_from(clone_url, self._repo_path, depth=1)
            else:
                raise

        logger.info(f"[Fix] Cloned to {self._repo_path}")
        self._detect_framework_and_language()

    def _detect_framework_and_language(self):
        if not self._repo_path or not os.path.exists(self._repo_path):
            return

        import json

        # 1. Check for Node.js (JavaScript/TypeScript)
        package_json_path = os.path.join(self._repo_path, "package.json")
        if os.path.exists(package_json_path):
            self.language = "javascript"
            self.detected_framework = "express"  # default fallback for node
            try:
                with open(package_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    if "express" in deps:
                        self.detected_framework = "express"
                    elif "fastify" in deps:
                        self.detected_framework = "fastify"
                    elif "@nestjs/core" in deps:
                        self.detected_framework = "nestjs"
                    elif "next" in deps:
                        self.detected_framework = "nextjs"
            except Exception as e:
                logger.error(f"[Fix] Error reading package.json: {e}")

            # Check if typescript is used
            tsconfig = os.path.join(self._repo_path, "tsconfig.json")
            if os.path.exists(tsconfig):
                self.language = "typescript"
            return

        # 2. Check for Python
        py_indicators = ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py"]
        has_py_file = any(os.path.exists(os.path.join(self._repo_path, ind)) for ind in py_indicators)
        if not has_py_file:
            # Check if any .py files exist in the repo
            for root, dirs, files in os.walk(self._repo_path):
                if any(f.endswith(".py") for f in files):
                    has_py_file = True
                    break

        if has_py_file:
            self.language = "python"
            self.detected_framework = "fastapi"  # default fallback
            # Try to read requirements.txt to detect framework
            req_path = os.path.join(self._repo_path, "requirements.txt")
            if os.path.exists(req_path):
                try:
                    with open(req_path, "r", encoding="utf-8") as f:
                        content = f.read().lower()
                        if "fastapi" in content:
                            self.detected_framework = "fastapi"
                        elif "flask" in content:
                            self.detected_framework = "flask"
                        elif "django" in content:
                            self.detected_framework = "django"
                except Exception as e:
                    logger.error(f"[Fix] Error reading requirements.txt: {e}")
            return

        # 3. Check for Go
        if os.path.exists(os.path.join(self._repo_path, "go.mod")):
            self.language = "go"
            self.detected_framework = "standard"
            return

        # 4. Check for Ruby
        if os.path.exists(os.path.join(self._repo_path, "Gemfile")):
            self.language = "ruby"
            self.detected_framework = "rails"
            return

    def _get_lang_rules(self) -> str:
        if self.language == "python":
            return """- CRITICAL: If you use `logger`, you MUST include BOTH `import logging` AND `logger = logging.getLogger(__name__)` in imports_needed. The import alone is NOT enough.
- Use `if value is not None:` instead of `if value:` when the value could legitimately be 0."""
        elif self.language in ("javascript", "typescript"):
            return """- CRITICAL: If you use a logger (like `console` or a logging library), make sure any required imports or setups are in imports_needed.
- Use strict equality checks `value !== null && value !== undefined` instead of `if (value)` when the value could legitimately be 0 or an empty string."""
        elif self.language == "go":
            return """- CRITICAL: Make sure all packages needed (e.g. "log", "fmt") are included in imports_needed.
- Handle zero values correctly according to Go idiom (e.g. checking for nil vs empty structs)."""
        else:
            return "- CRITICAL: Ensure all required external libraries/modules/packages are included in imports_needed."

    def _locate_endpoint_programmatically(self, endpoint_path: str, method: str) -> dict:
        """
        Attempts to programmatically find the file, start_line, end_line, and original_code
        of the given endpoint using file scanning and simple AST/regex heuristics.
        Returns a dict with keys: file_path, start_line, end_line, original_code
        or None if not found.
        """
        if not self._repo_path or not os.path.exists(self._repo_path):
            return None

        # Format endpoint path for lookup (standardizing trailing slashes)
        path = endpoint_path.strip()
        path_variants = [path]
        if path.endswith("/"):
            path_variants.append(path[:-1])
        else:
            path_variants.append(path + "/")

        # For Node/Express, path might have :param instead of {param}
        # e.g., /users/{user_id} -> /users/:user_id
        import re
        express_path = re.sub(r'\{([^}]+)\}', r':\1', path)
        if express_path not in path_variants:
            path_variants.append(express_path)

        repo_path = Path(self._repo_path)
        
        # Scan source files
        extensions = (".py", ".js", ".ts", ".tsx", ".go", ".java", ".rb")
        for ext in extensions:
            for f in repo_path.rglob(f"*{ext}"):
                if any(p in str(f) for p in [".git", "node_modules", "__pycache__", "venv", "backend", "frontend", ".gemini", "artifacts", "scratch", "brain"]):
                    continue
                try:
                    content = f.read_text(encoding="utf-8")
                    # Check if any path variant is in the file content
                    if not any(variant in content for variant in path_variants):
                        continue

                    import re
                    lines = content.splitlines()
                    for idx, line in enumerate(lines):
                        # Extract quoted strings in the line to match the path precisely
                        quoted_strings = re.findall(r'["\']([^"\']+)["\']', line)
                        path_matched = False
                        if quoted_strings:
                            for q in quoted_strings:
                                q_clean = q.strip().rstrip('/')
                                for variant in path_variants:
                                    v_clean = variant.rstrip('/')
                                    if q_clean == v_clean:
                                        path_matched = True
                                        break
                                if path_matched:
                                    break
                        else:
                            if any(variant in line for variant in path_variants):
                                path_matched = True

                        if path_matched:
                            # Let's verify if the method matches (case-insensitive check)
                            # e.g. app.get, @router.post, r.GET, GetMapping
                            lower_line = line.lower()
                            method_call = f".{method.lower()}("
                            method_call_upper = f".{method.upper()}("
                            is_route = (
                                "@" in line or
                                "app." in lower_line or
                                "router." in lower_line or
                                "route" in lower_line or
                                method_call in line or
                                method_call_upper in line
                            )
                            if is_route and (method.lower() in lower_line or any(m in lower_line for m in [".route", "request"])):
                                # We found the decorator/definition line!
                                start_idx = idx
                                # Now backtrack to find any leading decorators/annotations
                                while start_idx > 0:
                                    prev_line = lines[start_idx - 1].strip()
                                    if prev_line.startswith("@") or prev_line.startswith("["):
                                        start_idx -= 1
                                    else:
                                        break
                                
                                # Now find the end of the function/block
                                end_idx = idx
                                if ext == ".py":
                                    # For python, read until the indentation level goes back to <= start line indentation
                                    # Find the def line first to get base indentation (matching def or async def)
                                    def_line_idx = idx
                                    while def_line_idx < len(lines) and not lines[def_line_idx].strip().startswith(("def ", "async def ")):
                                        def_line_idx += 1
                                    if def_line_idx >= len(lines):
                                        def_line_idx = idx # fallback
                                    
                                    # Get base indentation
                                    def_line = lines[def_line_idx]
                                    base_indent = len(def_line) - len(def_line.lstrip())
                                    
                                    end_idx = def_line_idx + 1
                                    while end_idx < len(lines):
                                        curr_line = lines[end_idx]
                                        if not curr_line.strip():
                                            end_idx += 1
                                            continue
                                        curr_indent = len(curr_line) - len(curr_line.lstrip())
                                        # If indentation is less than or equal to def base indentation, we hit the end
                                        if curr_indent <= base_indent and not curr_line.strip().startswith((")", "]", "}")):
                                            break
                                        end_idx += 1
                                else:
                                    # For JS/Go/Java, match braces { and }
                                    brace_count = 0
                                    found_braces = False
                                    for scan_idx in range(idx, len(lines)):
                                        scan_line = lines[scan_idx]
                                        brace_count += scan_line.count("{") - scan_line.count("}")
                                        if "{" in scan_line:
                                            found_braces = True
                                        if found_braces and brace_count <= 0:
                                            end_idx = scan_idx + 1
                                            break
                                    if end_idx == idx:
                                        # Fallback: scan 30 lines
                                        end_idx = min(len(lines), idx + 30)

                                original_lines = lines[start_idx:end_idx]
                                return {
                                    "file_path": str(f.relative_to(repo_path)).replace("\\", "/"),
                                    "target_function": "",
                                    "start_line": start_idx + 1,
                                    "end_line": end_idx,
                                    "original_code": "\n".join(original_lines),
                                    "reasoning": f"Programmatically matched path '{endpoint_path}' and method '{method}' in {f.name}"
                                }
                except Exception as e:
                    logger.warning(f"[Fix] Error scanning file {f} for programmatic search: {e}")
                    continue
        return None

    def _cleanup(self):
        """Remove temp directory."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)

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

    async def _list_source_files(self, extension: str = None) -> dict:
        try:
            repo_path = Path(self._repo_path)
            # If the caller asks for the default ".py" but the detected language is different,
            # we should adjust the default to match the detected language.
            if extension is None or extension == ".py":
                if self.language != "python":
                    if self.language in ("javascript", "typescript"):
                        extension = ".js"
                    elif self.language == "go":
                        extension = ".go"
                    elif self.language == "ruby":
                        extension = ".rb"
                    else:
                        extension = ".py"
            if extension is None:
                extension = ".py"
                
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
            # Scan common source file extensions
            for ext in ("*.py", "*.js", "*.ts", "*.tsx", "*.go", "*.rb", "*.java", "*.kt", "*.cs"):
                for f in repo_path.rglob(ext):
                    if ".git" in str(f) or "__pycache__" in str(f) or "node_modules" in str(f):
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
