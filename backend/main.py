from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.core.config import get_settings
from backend.core.websocket_manager import ws_manager
from backend.db.session import init_db
from backend.api import sessions, reports, github, auth

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Chaos Agent...")
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("Chaos Agent stopped.")


app = FastAPI(
    title="Chaos Agent",
    description="Autonomous API failure injection and error handling code generator",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(github.router, prefix="/api/github", tags=["github"])


@app.websocket("/ws/{session_id}")
async def websocket_session(ws: WebSocket, session_id: str):
    await ws_manager.connect(ws, session_id)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws, session_id)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "chaos-agent",
        "github_integration": bool(settings.github_token),
    }
