import json
from typing import Dict, Set
from fastapi import WebSocket
from loguru import logger


class WebSocketManager:
    def __init__(self):
        # session_id -> set of websockets
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, session_id: str):
        await ws.accept()
        self._connections.setdefault(session_id, set()).add(ws)
        logger.info(f"WS connected: session {session_id}")

    def disconnect(self, ws: WebSocket, session_id: str):
        if session_id in self._connections:
            self._connections[session_id].discard(ws)

    async def broadcast(self, session_id: str, event_type: str, payload: dict):
        message = json.dumps({"type": event_type, "payload": payload})
        dead = set()
        for ws in self._connections.get(session_id, set()):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections.get(session_id, set()).discard(ws)

    # ── Convenience emitters ──────────────────────────────────────────────────

    async def emit_agent_step(self, session_id: str, agent: str,
                               step_type: str, content: str,
                               tool_name: str = None, tool_output=None):
        await self.broadcast(session_id, "agent_step", {
            "agent": agent,
            "step_type": step_type,   # thought | tool_call | observation | conclusion
            "content": content,
            "tool_name": tool_name,
            "tool_output": tool_output,
        })

    async def emit_failure_result(self, session_id: str, failure: dict):
        await self.broadcast(session_id, "failure_result", failure)

    async def emit_status(self, session_id: str, status: str, message: str = ""):
        await self.broadcast(session_id, "status", {"status": status, "message": message})

    async def emit_report_ready(self, session_id: str, report_id: str):
        await self.broadcast(session_id, "report_ready", {"report_id": report_id})


ws_manager = WebSocketManager()
