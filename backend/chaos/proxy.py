import asyncio
import json
import time
import httpx
from loguru import logger


class ChaosProxy:
    """
    Injects failure modes by making real HTTP calls to the target app
    and simulating dependency failures through a mock proxy layer.

    How it works:
    - For network/dependency failures: sends specially crafted requests
      to the target app with headers that signal mock dependency behaviour
    - For direct endpoint testing: calls the endpoint directly and
      measures how it handles various bad inputs
    """

    def __init__(self, target_base_url: str):
        self.base_url = target_base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=15.0)

    async def inject_failure(
        self,
        failure_mode_id: str,
        endpoint_path: str,
        method: str = "GET",
        payload: dict = None,
    ) -> dict:
        """
        Inject a specific failure mode against a specific endpoint.
        Returns observation data about how the app responded.
        """
        url = f"{self.base_url}{endpoint_path}"
        start_time = time.time()

        try:
            result = await self._execute_failure(
                failure_mode_id, url, method, payload
            )
        except Exception as e:
            result = {
                "failure_mode": failure_mode_id,
                "endpoint": endpoint_path,
                "method": method,
                "error": str(e),
                "status_code": None,
                "response_body": None,
                "response_time_ms": int((time.time() - start_time) * 1000),
                "observation": "injection_error",
            }

        result["response_time_ms"] = int((time.time() - start_time) * 1000)
        return result

    async def _execute_failure(
        self, failure_mode: str, url: str, method: str, payload: dict
    ) -> dict:
        headers = {"X-Chaos-Mode": failure_mode, "Content-Type": "application/json"}

        # ── Network failures ──────────────────────────────────────────────────
        if failure_mode == "http_timeout":
            # Send request with a very short timeout to simulate timeout scenario
            try:
                async with httpx.AsyncClient(timeout=0.001) as c:
                    await c.request(method, url, json=payload, headers=headers)
            except httpx.TimeoutException:
                return self._build_result(failure_mode, url, method,
                                          None, "Request timed out (as expected — checking app handles this)")

        if failure_mode == "slow_response":
            # Add delay header — app should handle slow upstream
            headers["X-Chaos-Delay"] = "5000"
            try:
                async with httpx.AsyncClient(timeout=2.0) as c:
                    r = await c.request(method, url, json=payload, headers=headers)
                    return self._build_result(failure_mode, url, method, r)
            except httpx.TimeoutException:
                return self._build_result(failure_mode, url, method,
                                          None, "Client timeout — app didn't handle slow upstream")

        if failure_mode == "connection_refused":
            # Try to connect to a port that should be closed
            try:
                async with httpx.AsyncClient(timeout=3.0) as c:
                    r = await c.get("http://localhost:19999/unreachable")
                    return self._build_result(failure_mode, url, method, r)
            except httpx.ConnectError:
                return self._build_result(failure_mode, url, method,
                                          None, "Connection refused — checking if app handles dependency outage")

        # ── Direct endpoint probing ───────────────────────────────────────────
        if failure_mode == "malformed_json":
            # Send malformed JSON body
            raw_client = httpx.AsyncClient(timeout=10.0)
            headers["Content-Type"] = "application/json"
            r = await raw_client.request(
                method, url,
                content=b'{"broken": json, missing: quotes}',
                headers=headers
            )
            await raw_client.aclose()
            return self._build_result(failure_mode, url, method, r)

        if failure_mode == "empty_response":
            headers["X-Chaos-Empty-Response"] = "true"
            r = await self.client.request(method, url, json=payload, headers=headers)
            return self._build_result(failure_mode, url, method, r)

        if failure_mode == "null_fields":
            # Send payload with all values set to null
            null_payload = {k: None for k in (payload or {"id": None})}
            r = await self.client.request(method, url, json=null_payload, headers=headers)
            return self._build_result(failure_mode, url, method, r)

        if failure_mode == "wrong_content_type":
            headers["Content-Type"] = "text/html"
            r = await self.client.request(
                method, url,
                content=b"<html><body>not json</body></html>",
                headers=headers
            )
            return self._build_result(failure_mode, url, method, r)

        # ── Dependency simulation via headers ─────────────────────────────────
        # For http_500, http_429, http_503, http_401, http_404,
        # db_connection_drop, db_timeout, db_constraint_violation,
        # partial_response, dns_failure, connection_reset
        # We send the failure mode as a header and the app's chaos middleware
        # (which we inject into the target) handles the simulation
        r = await self.client.request(method, url, json=payload, headers=headers)
        return self._build_result(failure_mode, url, method, r)

    def _build_result(
        self, failure_mode: str, url: str, method: str,
        response: httpx.Response | None, note: str = None
    ) -> dict:
        if response is None:
            return {
                "failure_mode": failure_mode,
                "endpoint": url,
                "method": method,
                "status_code": None,
                "response_body": note or "No response received",
                "headers": {},
                "observation": "no_response",
                "error_leaked": False,
                "stack_trace_leaked": False,
            }

        body = ""
        try:
            body = response.text[:2000]
        except Exception:
            body = "<unreadable>"

        error_leaked = self._check_error_leaked(response.status_code, body)
        stack_leaked = self._check_stack_leaked(body)

        return {
            "failure_mode": failure_mode,
            "endpoint": url,
            "method": method,
            "status_code": response.status_code,
            "response_body": body,
            "headers": dict(response.headers),
            "observation": self._classify_observation(response.status_code, body),
            "error_leaked": error_leaked,
            "stack_trace_leaked": stack_leaked,
        }

    def _check_error_leaked(self, status_code: int | None, body: str) -> bool:
        """Did an internal error message leak into the response?"""
        if status_code in (500, 502, 503):
            leak_phrases = [
                "traceback", "exception", "error at", "internal server",
                "sqlalchemy", "postgresql", "database", "connection refused",
                "stack trace", "line ", "file \""
            ]
            body_lower = body.lower()
            return any(phrase in body_lower for phrase in leak_phrases)
        return False

    def _check_stack_leaked(self, body: str) -> bool:
        """Did a full stack trace leak?"""
        indicators = ["Traceback (most recent call last)", "at Object.", "at Module."]
        return any(ind in body for ind in indicators)

    def _classify_observation(self, status_code: int | None, body: str) -> str:
        if status_code is None:
            return "no_response"
        if status_code in (200, 201, 204):
            return "handled_gracefully"
        if status_code in (400, 422):
            return "validation_error_returned"
        if status_code in (500, 502, 503):
            if self._check_error_leaked(status_code, body):
                return "unhandled_error_leaked"
            return "server_error_returned"
        if status_code == 429:
            return "rate_limit_propagated"
        if status_code == 503:
            return "service_unavailable_returned"
        return f"status_{status_code}"

    async def close(self):
        await self.client.aclose()
