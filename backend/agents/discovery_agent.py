"""
Discovery Agent

Builds the endpoint list using industry-standard API specification formats.
Supports the same input methods used by Postman, Datadog, Gremlin, and k6:

  1. OpenAPI spec URL   — paste the URL to your /openapi.json or /swagger.yaml
  2. OpenAPI file       — upload your openapi.json or swagger.yaml
  3. Postman Collection — export from Postman, upload the JSON
  4. Manual entry       — add endpoints one by one (fallback)

No code scanning. No guessing. No token waste.
"""

import uuid
import json
import yaml
import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Endpoint, ChaosSession, SessionStatus

DEPENDENCY_SIGNALS = {
    "database":    ["db", "database", "sql", "user", "account", "record",
                    "store", "save", "fetch", "query", "find", "create"],
    "payment_api": ["payment", "charge", "billing", "invoice",
                    "subscribe", "checkout", "stripe", "paystack"],
    "redis":       ["cache", "session", "token", "rate"],
    "email":       ["email", "notify", "alert", "verify", "confirm"],
    "ai_api":      ["recommend", "generate", "predict", "embed",
                    "classify", "summarize", "ai", "ml"],
    "storage":     ["upload", "file", "image", "media", "attachment", "download"],
    "external_api":["webhook", "callback", "integration", "sync", "import", "export"],
}

LOW_VALUE_PATHS = {
    "/health", "/ping", "/status", "/ready", "/live",
    "/docs", "/openapi.json", "/swagger.json", "/swagger",
    "/favicon.ico", "/robots.txt", "/metrics",
}


class DiscoveryAgent:
    """
    Parses API specs into a clean, prioritised endpoint list.
    No LLM calls needed — spec parsing is deterministic.
    """

    def __init__(self, db: AsyncSession = None, session_id: str = ""):
        self.db = db
        self.session_id = session_id

    # ── Public entry points (Classic/Compatible) ─────────────────────────────────

    async def from_openapi_url(self, spec_url: str) -> list[dict]:
        """Method 1: Fetch, parse and save an OpenAPI spec from a URL."""
        logger.info(f"[Discovery] Fetching OpenAPI spec from {spec_url}")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(spec_url)
                r.raise_for_status()
                content_type = r.headers.get("content-type", "")
                if "yaml" in content_type or spec_url.endswith((".yaml", ".yml")):
                    spec = yaml.safe_load(r.text)
                else:
                    spec = r.json()
            raw_endpoints = await self._parse_openapi_raw(spec, source=spec_url)
            return await self._save_endpoints(raw_endpoints)
        except Exception as e:
            logger.error(f"[Discovery] OpenAPI URL fetch failed: {e}")
            raise ValueError(f"Could not fetch OpenAPI spec from {spec_url}: {e}")

    async def from_openapi_content(self, content: str | dict) -> list[dict]:
        """Method 2: Parse and save an uploaded OpenAPI spec."""
        logger.info("[Discovery] Parsing uploaded OpenAPI spec")
        try:
            if isinstance(content, dict):
                spec = content
            elif content.strip().startswith("{"):
                spec = json.loads(content)
            else:
                spec = yaml.safe_load(content)
            raw_endpoints = await self._parse_openapi_raw(spec, source="uploaded_file")
            return await self._save_endpoints(raw_endpoints)
        except Exception as e:
            raise ValueError(f"Could not parse OpenAPI spec: {e}")

    async def from_postman_collection(self, collection: str | dict) -> list[dict]:
        """Method 3: Parse and save an exported Postman Collection v2.1 JSON."""
        logger.info("[Discovery] Parsing Postman Collection")
        try:
            if isinstance(collection, str):
                data = json.loads(collection)
            else:
                data = collection
            raw_endpoints = await self._parse_postman_raw(data)
            return await self._save_endpoints(raw_endpoints)
        except Exception as e:
            raise ValueError(f"Could not parse Postman Collection: {e}")

    async def from_manual_endpoints(self, endpoints: list[dict]) -> list[dict]:
        """Method 4: User-provided endpoint list from the UI (save directly)."""
        logger.info(f"[Discovery] Using {len(endpoints)} manually entered endpoints")
        raw_endpoints = []
        for ep in endpoints:
            raw_endpoints.append({
                "path": ep.get("path", "/"),
                "method": ep.get("method", "GET").upper(),
                "description": ep.get("description", ""),
                "sample_payload": ep.get("payload"),
                "dependencies": self._detect_dependencies(ep.get("path", "")),
            })
        return await self._save_endpoints(raw_endpoints)

    # ── Preview entry points (DB-free) ───────────────────────────────────────────

    async def preview_from_openapi_url(self, spec_url: str) -> dict:
        """Fetch and parse OpenAPI spec from URL, return grouped by tag preview."""
        logger.info(f"[Discovery] Previewing OpenAPI spec from {spec_url}")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(spec_url)
                r.raise_for_status()
                content_type = r.headers.get("content-type", "")
                if "yaml" in content_type or spec_url.endswith((".yaml", ".yml")):
                    spec = yaml.safe_load(r.text)
                else:
                    spec = r.json()
            raw_endpoints = await self._parse_openapi_raw(spec, source=spec_url)
            return self.group_and_enrich_endpoints(raw_endpoints, "openapi_url")
        except Exception as e:
            logger.error(f"[Discovery] OpenAPI URL fetch failed: {e}")
            raise ValueError(f"Could not fetch OpenAPI spec from {spec_url}: {e}")

    async def preview_from_openapi_content(self, content: str | dict) -> dict:
        """Parse uploaded OpenAPI spec content, return grouped by tag preview."""
        logger.info("[Discovery] Previewing uploaded OpenAPI spec")
        try:
            if isinstance(content, dict):
                spec = content
            elif content.strip().startswith("{"):
                spec = json.loads(content)
            else:
                spec = yaml.safe_load(content)
            raw_endpoints = await self._parse_openapi_raw(spec, source="uploaded_file")
            return self.group_and_enrich_endpoints(raw_endpoints, "openapi_file")
        except Exception as e:
            raise ValueError(f"Could not parse OpenAPI spec: {e}")

    async def preview_from_postman(self, collection: str | dict) -> dict:
        """Parse Postman Collection export, return grouped by tag preview."""
        logger.info("[Discovery] Previewing Postman Collection")
        try:
            if isinstance(collection, str):
                data = json.loads(collection)
            else:
                data = collection
            raw_endpoints = await self._parse_postman_raw(data)
            return self.group_and_enrich_endpoints(raw_endpoints, "postman")
        except Exception as e:
            raise ValueError(f"Could not parse Postman Collection: {e}")

    async def preview_from_manual(self, endpoints: list[dict]) -> dict:
        """Process manual endpoint inputs, return grouped by tag preview under 'Manual'."""
        logger.info(f"[Discovery] Previewing {len(endpoints)} manual endpoints")
        raw_endpoints = []
        for ep in endpoints:
            raw_endpoints.append({
                "path": ep.get("path", "/"),
                "method": ep.get("method", "GET").upper(),
                "description": ep.get("description", ""),
                "sample_payload": ep.get("payload"),
                "dependencies": self._detect_dependencies(ep.get("path", "")),
                "folder_tag": "Manual"
            })
        return self.group_and_enrich_endpoints(raw_endpoints, "manual")

    # ── Grouping and Enrichment Helper ──────────────────────────────────────────

    def group_and_enrich_endpoints(self, raw_endpoints: list[dict], method_name: str) -> dict:
        """Deduplicates, tags, and flags endpoints (with risk scores/recommends)."""
        draft_id = str(uuid.uuid4())
        
        seen = set()
        deduped = []
        for ep in raw_endpoints:
            key = f"{ep['method'].upper()}:{ep['path']}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(ep)
            
        groups_map = {}
        for ep in deduped:
            method = ep["method"].upper()
            path = ep["path"]
            
            # Tags
            tags = ep.get("tags", [])
            tag = tags[0] if tags else ep.get("folder_tag", "General")
            
            # Slugify temp_id
            path_slug = self._slugify(path)
            temp_id = f"{method.lower()}-{path_slug}" if path_slug else method.lower()
            
            recommended, risk_note = self._check_recommendation(
                method, path, ep.get("operation_id", ""), ep.get("tags", [])
            )
            
            enriched = {
                "temp_id": temp_id,
                "path": path,
                "method": method,
                "description": ep.get("description", ""),
                "sample_payload": ep.get("sample_payload"),
                "dependencies": ep.get("dependencies", ["database"]),
                "recommended": recommended,
                "risk_note": risk_note,
            }
            
            if tag not in groups_map:
                groups_map[tag] = []
            groups_map[tag].append(enriched)
            
        groups = []
        for tag, endpoints in groups_map.items():
            groups.append({
                "tag": tag,
                "endpoints": endpoints
            })
            
        # Store flat list of all enriched endpoints under the draft_id
        flat_endpoints = []
        for g in groups:
            flat_endpoints.extend(g["endpoints"])
            
        draft_data = {
            "method": method_name,
            "endpoints": flat_endpoints,
        }
        
        from backend.core.draft_cache import draft_cache
        draft_cache.set(draft_id, draft_data)
        
        return {
            "draft_id": draft_id,
            "method": method_name,
            "total_endpoints": len(deduped),
            "groups": groups
        }

    # ── OpenAPI parser (raw) ───────────────────────────────────────────────────

    async def _parse_openapi_raw(self, spec: dict, source: str) -> list[dict]:
        """Handles OpenAPI 3.x and Swagger 2.x without database saves."""
        version = spec.get("openapi", spec.get("swagger", ""))
        logger.info(f"[Discovery] OpenAPI version: {version} from {source}")

        endpoints = []
        paths = spec.get("paths", {})

        for path, path_item in paths.items():
            if path.lower() in LOW_VALUE_PATHS:
                continue
            if any(path.lower().startswith(lv) for lv in
                   ["/docs", "/swagger", "/redoc", "/static"]):
                continue

            for method in ["get", "post", "put", "delete", "patch", "head", "options"]:
                operation = path_item.get(method)
                if not operation:
                    continue

                summary = operation.get("summary", "")
                description = operation.get("description", "")
                tags = operation.get("tags", [])

                sample_payload = None
                if method in ("post", "put", "patch"):
                    sample_payload = self._extract_sample_payload(operation, spec)

                context = f"{path} {summary} {description} {' '.join(tags)}"
                dependencies = self._detect_dependencies(context)

                parameters = operation.get("parameters", [])
                path_params = [p["name"] for p in parameters
                               if p.get("in") == "path"]

                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "description": summary or description or f"{method.upper()} {path}",
                    "sample_payload": sample_payload,
                    "dependencies": dependencies,
                    "tags": tags,
                    "path_params": path_params,
                    "operation_id": operation.get("operationId", ""),
                })

        logger.info(f"[Discovery] Parsed {len(endpoints)} endpoints from OpenAPI spec")
        return endpoints

    def _extract_sample_payload(self, operation: dict, full_spec: dict) -> dict | None:
        """Build a sample request body from the operation's requestBody schema."""
        request_body = operation.get("requestBody", {})
        if not request_body:
            return None

        content = request_body.get("content", {})
        json_schema = (
            content.get("application/json", {})
            .get("schema", {})
        )

        if not json_schema:
            return None

        return self._schema_to_example(json_schema, full_spec, depth=0)

    def _schema_to_example(self, schema: dict, full_spec: dict,
                            depth: int = 0) -> dict | list | str | int | bool | None:
        """Recursively generate example data from a JSON Schema."""
        if depth > 3:
            return None

        # Resolve $ref
        if "$ref" in schema:
            ref = schema["$ref"].lstrip("#/").split("/")
            resolved = full_spec
            try:
                for key in ref:
                    resolved = resolved[key]
                schema = resolved
            except (KeyError, TypeError):
                return {}

        # Use provided example first
        if "example" in schema:
            return schema["example"]

        schema_type = schema.get("type", "object")
        props = schema.get("properties", {})

        if schema_type == "object" or props:
            result = {}
            for prop_name, prop_schema in props.items():
                result[prop_name] = self._schema_to_example(
                    prop_schema, full_spec, depth + 1
                )
            return result or {}

        if schema_type == "array":
            items = schema.get("items", {})
            return [self._schema_to_example(items, full_spec, depth + 1)]

        # Scalar types
        fmt = schema.get("format", "")
        enum = schema.get("enum", [])
        if enum:
            return enum[0]
        if schema_type == "string":
            if fmt == "email":
                return "user@example.com"
            if fmt == "password":
                return "password123"
            if fmt == "date-time":
                return "2025-01-01T00:00:00Z"
            if fmt == "uuid":
                return "550e8400-e29b-41d4-a716-446655440000"
            return f"sample_{schema.get('title', 'value').lower().replace(' ', '_')}"
        if schema_type == "integer":
            return schema.get("minimum", 1)
        if schema_type == "number":
            return 1.0
        if schema_type == "boolean":
            return True

        return None

    # ── Postman Collection parser (raw) ────────────────────────────────────────

    async def _parse_postman_raw(self, collection: dict) -> list[dict]:
        """Parse Postman Collection without DB saves."""
        info = collection.get("info", {})
        logger.info(f"[Discovery] Postman collection: {info.get('name', 'Unnamed')}")

        raw_items = collection.get("item", [])
        requests = self._flatten_postman_items(raw_items)

        endpoints = []
        for req in requests:
            request = req.get("request", {})
            if not request:
                continue

            method = request.get("method", "GET").upper()
            url_data = request.get("url", {})

            if isinstance(url_data, str):
                path = self._postman_url_to_path(url_data)
            else:
                raw_path = url_data.get("path", [])
                if isinstance(raw_path, list):
                    path = "/" + "/".join(
                        f"{{{seg.strip(':')}}}" if seg.startswith(":") else seg
                        for seg in raw_path
                        if seg
                    )
                else:
                    path = str(raw_path)

            if not path:
                continue

            sample_payload = None
            body = request.get("body", {})
            if body and body.get("mode") == "raw":
                raw_body = body.get("raw", "")
                if raw_body.strip():
                    try:
                        sample_payload = json.loads(raw_body)
                    except Exception:
                        pass

            name = req.get("name", f"{method} {path}")
            deps = self._detect_dependencies(f"{path} {name}")
            tag = req.get("folder_tag", "General")

            endpoints.append({
                "path": path,
                "method": method,
                "description": name,
                "sample_payload": sample_payload,
                "dependencies": deps,
                "folder_tag": tag,
            })

        logger.info(f"[Discovery] Parsed {len(endpoints)} requests from Postman Collection")
        return endpoints

    def _flatten_postman_items(self, items: list, parent_folder: str = "General") -> list[dict]:
        """Recursively flatten Postman folder structure."""
        result = []
        for item in items:
            if "item" in item:
                result.extend(self._flatten_postman_items(
                    item["item"], parent_folder=item.get("name", "General")
                ))
            else:
                item_copy = dict(item)
                item_copy["folder_tag"] = parent_folder
                result.append(item_copy)
        return result

    def _postman_url_to_path(self, url: str) -> str:
        """Extract just the path from a full URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path = parsed.path or "/"
            path = "/".join(
                f"{{{seg.lstrip(':')}}}" if seg.startswith(":") else seg
                for seg in path.split("/")
            )
            return path or "/"
        except Exception:
            return "/"

    # ── Shared utilities ──────────────────────────────────────────────────────

    def _detect_dependencies(self, context: str) -> list[str]:
        context_lower = context.lower()
        found = []
        for dep, signals in DEPENDENCY_SIGNALS.items():
            if any(s in context_lower for s in signals):
                found.append(dep)
        return found or ["database"]

    def _slugify(self, text: str) -> str:
        import re
        t = text.lower()
        t = re.sub(r'[^a-z0-9_-]', '-', t)
        t = re.sub(r'-+', '-', t)
        return t.strip('-')

    def _check_recommendation(self, method: str, path: str, operation_id: str = "", tags: list[str] = []) -> tuple[bool, str | None]:
        method_upper = method.upper()
        is_delete = method_upper == "DELETE"
        
        match_terms = ["admin", "impersonate", "webhook", "vault", "subscription", "platform-admin", "delete", "destroy", "remove"]
        
        path_lower = path.lower()
        op_lower = operation_id.lower() if operation_id else ""
        tags_lower = [t.lower() for t in tags]
        
        found_term = None
        for term in match_terms:
            if term in path_lower or term in op_lower or any(term in t for t in tags_lower):
                found_term = term
                break
                
        if is_delete or found_term:
            if is_delete or found_term in ["delete", "destroy", "remove"]:
                note = "Destructive endpoint — deletes or removes resources"
            elif found_term in ["admin", "platform-admin"]:
                note = "Admin endpoint — modifies platform or administrative state"
            elif found_term == "impersonate":
                note = "Privileged endpoint — performs actions on behalf of other users"
            elif found_term == "webhook":
                note = "Webhook callback endpoint"
            elif found_term == "vault":
                note = "Security sensitive — accesses secrets or credentials"
            elif found_term == "subscription":
                note = "Payment/Subscription operation"
            else:
                note = f"Potential sensitive action ({found_term})"
            return False, note
            
        return True, None

    async def _save_endpoints(self, endpoints: list[dict]) -> list[dict]:
        """Internal helper to save list to DB (classic compatibility)."""
        saved = []
        seen = set()

        for ep in endpoints:
            key = f"{ep['method']}:{ep['path']}"
            if key in seen:
                continue
            seen.add(key)

            db_endpoint = Endpoint(
                id=str(uuid.uuid4()),
                session_id=self.session_id,
                path=ep["path"],
                method=ep["method"].upper(),
                description=ep.get("description", ""),
                sample_payload=ep.get("sample_payload"),
                dependencies=ep.get("dependencies", ["database"]),
            )
            self.db.add(db_endpoint)
            saved.append(db_endpoint)

        await self.db.flush()

        session = await self.db.get(ChaosSession, self.session_id)
        if session:
            session.endpoints_found = len(saved)
            await self.db.flush()

        logger.info(f"[Discovery] Saved {len(saved)} endpoints")
        return [
            {
                "id": e.id,
                "path": e.path,
                "method": e.method,
                "description": e.description,
                "dependencies": e.dependencies,
                "sample_payload": e.sample_payload,
            }
            for e in saved
        ]

    async def save_selected_endpoints(self, endpoints: list[dict]) -> list[dict]:
        """Save user-selected endpoints list to DB."""
        return await self._save_endpoints(endpoints)

    async def handle(self, *args, **kwargs):
        pass
