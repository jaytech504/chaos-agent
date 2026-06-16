import uuid
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent, Tool
from backend.chaos.proxy import ChaosProxy
from backend.chaos.failure_modes import FAILURE_MODES, get_failure_mode
from backend.db.models import FailureResult, FailureStatus, ChaosSession, SessionStatus
from backend.core.websocket_manager import ws_manager


class ChaosAgent(BaseAgent):
    """
    Selects and injects failure modes against each endpoint.
    Uses Qwen to reason about which failures are most relevant
    based on the endpoint's dependencies.
    """
    name = "chaos"
    system_prompt = """You are the Chaos Agent in a chaos engineering system.
Your job is to select the most relevant failure modes to inject against each endpoint.

Available failure categories:
- network: timeout, connection_refused, dns_failure, slow_response, connection_reset
- dependency: http_500, http_429, http_503, http_401, http_404
- data: malformed_json, empty_response, wrong_content_type, partial_response, null_fields
- resource: db_connection_drop, db_timeout, db_constraint_violation

Rules:
- If endpoint has "database" dependency → always include db_connection_drop, db_timeout
- If endpoint calls external APIs → include http_500, http_429, http_timeout
- If endpoint accepts POST/PUT body → always include malformed_json, null_fields
- For ALL endpoints → include http_500, slow_response, empty_response
- Prioritise failures most likely to expose real bugs

Return JSON:
{
  "selected_failures": ["failure_mode_id_1", "failure_mode_id_2", ...]
}"""

    def __init__(self, db: AsyncSession, session_id: str, target_url: str):
        super().__init__(db, session_id)
        self.proxy = ChaosProxy(target_url)
        self._register_tools()

    def _register_tools(self):
        self.register_tool(Tool(
            name="inject_failure",
            description="Inject a specific failure mode against an endpoint and observe the response",
            parameters={
                "type": "object",
                "properties": {
                    "failure_mode_id": {
                        "type": "string",
                        "description": "ID of the failure mode to inject",
                        "enum": [f.id for f in FAILURE_MODES],
                    },
                    "endpoint_path": {"type": "string"},
                    "method": {"type": "string", "default": "GET"},
                    "payload": {"type": "object", "description": "Request body if applicable"},
                },
                "required": ["failure_mode_id", "endpoint_path"],
            },
            func=self._inject_and_observe,
        ))

    async def _inject_and_observe(
        self, failure_mode_id: str, endpoint_path: str,
        method: str = "GET", payload: dict = None
    ) -> dict:
        result = await self.proxy.inject_failure(
            failure_mode_id, endpoint_path, method, payload
        )
        # Stream to frontend immediately so judges see it happening live
        await ws_manager.emit_failure_result(self.session_id, {
            "failure_mode": failure_mode_id,
            "endpoint": endpoint_path,
            "status_code": result.get("status_code"),
            "observation": result.get("observation"),
            "error_leaked": result.get("error_leaked", False),
        })
        return result

    async def handle(self, endpoints: list[dict]) -> list[dict]:
        """
        Run chaos injection against all endpoints.
        Returns list of FailureResult records.
        """
        await self._update_session_status(SessionStatus.INJECTING)
        all_results = []

        for endpoint in endpoints:
            results = await self._chaos_endpoint(endpoint)
            all_results.extend(results)

        # Update session counter
        session = await self.db.get(ChaosSession, self.session_id)
        if session:
            session.failures_injected = len(all_results)
            await self.db.flush()

        logger.info(f"[Chaos] Injected {len(all_results)} failures total")
        return all_results

    async def _chaos_endpoint(self, endpoint: dict) -> list[dict]:
        """Select and inject relevant failures for one endpoint."""
        # Ask Qwen which failures to use for this endpoint
        selection_result = await self.run(
            task=f"""Select failure modes for endpoint {endpoint['method']} {endpoint['path']}.
Dependencies: {endpoint.get('dependencies', [])}
Choose the most relevant failure modes to inject.""",
            context={"endpoint": endpoint}
        )

        selected = selection_result.get("selected_failures", [
            "http_500", "http_timeout", "malformed_json",
            "slow_response", "empty_response"
        ])

        # Cap at 8 per endpoint to keep demo runtime reasonable
        selected = selected[:8]

        results = []
        for failure_id in selected:
            failure_mode = get_failure_mode(failure_id)
            if not failure_mode:
                continue

            raw = await self._inject_and_observe(
                failure_mode_id=failure_id,
                endpoint_path=endpoint["path"],
                method=endpoint["method"],
                payload=endpoint.get("sample_payload"),
            )

            # Determine result classification
            observation = raw.get("observation", "")
            if observation in ("unhandled_error_leaked", "no_response"):
                result_status = FailureStatus.UNHANDLED
            elif observation in ("server_error_returned",) and raw.get("error_leaked"):
                result_status = FailureStatus.UNHANDLED
            elif raw.get("status_code") in (200, 201, 400, 422):
                result_status = FailureStatus.HANDLED
            else:
                result_status = FailureStatus.DEGRADED

            # Persist
            failure_record = FailureResult(
                id=str(uuid.uuid4()),
                session_id=self.session_id,
                endpoint_id=endpoint["id"],
                failure_mode=failure_id,
                failure_description=failure_mode.description,
                status_code_received=raw.get("status_code"),
                response_body=str(raw.get("response_body", ""))[:1000],
                response_time_ms=raw.get("response_time_ms"),
                result=result_status,
                error_leaked=raw.get("error_leaked", False),
                stack_trace_leaked=raw.get("stack_trace_leaked", False),
            )
            self.db.add(failure_record)
            await self.db.flush()

            results.append({
                "id": failure_record.id,
                "endpoint_id": endpoint["id"],
                "endpoint_path": endpoint["path"],
                "failure_mode": failure_id,
                "result": result_status.value,
                "status_code": raw.get("status_code"),
                "error_leaked": raw.get("error_leaked", False),
                "response_body": str(raw.get("response_body", ""))[:500],
            })

        return results

    async def _update_session_status(self, status: SessionStatus):
        session = await self.db.get(ChaosSession, self.session_id)
        if session:
            session.status = status
            await self.db.flush()

    async def close(self):
        await self.proxy.close()
