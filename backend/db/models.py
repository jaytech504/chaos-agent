from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, JSON, Enum, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    github_id = Column(Integer, unique=True, nullable=False)
    github_username = Column(String(100), nullable=False)
    github_avatar_url = Column(String(500), nullable=True)
    github_access_token = Column(String(500), nullable=False)
    email = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("ChaosSession", back_populates="user")


class SessionStatus(str, PyEnum):
    PENDING = "pending"
    DISCOVERING = "discovering"
    INJECTING = "injecting"
    ANALYSING = "analysing"
    FIXING = "fixing"
    OPENING_PRS = "opening_prs"
    COMPLETE = "complete"
    FAILED = "failed"


class FailureStatus(str, PyEnum):
    UNHANDLED = "unhandled"
    HANDLED = "handled"
    DEGRADED = "degraded"


class ChaosSession(Base):
    __tablename__ = "chaos_sessions"

    id = Column(String, primary_key=True)
    target_url = Column(String(500), nullable=False)
    target_name = Column(String(100), nullable=True)
    source_path = Column(String(500), nullable=True)
    github_repo = Column(String(300), nullable=True)    # owner/repo
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.PENDING)
    endpoints_found = Column(Integer, default=0)
    failures_injected = Column(Integer, default=0)
    unhandled_count = Column(Integer, default=0)
    fixes_generated = Column(Integer, default=0)
    prs_opened = Column(Integer, default=0)             # NEW
    risk_score = Column(Integer, default=0)             # NEW
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    endpoints = relationship("Endpoint", back_populates="session", cascade="all, delete-orphan")
    failures = relationship("FailureResult", back_populates="session", cascade="all, delete-orphan")
    agent_steps = relationship("AgentStep", back_populates="session", cascade="all, delete-orphan")
    report = relationship("Report", back_populates="session", uselist=False, cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="session", cascade="all, delete-orphan")
    user = relationship("User", back_populates="sessions")


class Endpoint(Base):
    __tablename__ = "endpoints"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chaos_sessions.id"), nullable=False)
    path = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False)
    description = Column(Text, nullable=True)
    sample_payload = Column(JSON, nullable=True)
    dependencies = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChaosSession", back_populates="endpoints")
    failures = relationship("FailureResult", back_populates="endpoint")


class FailureResult(Base):
    __tablename__ = "failure_results"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chaos_sessions.id"), nullable=False)
    endpoint_id = Column(String, ForeignKey("endpoints.id"), nullable=False)
    failure_mode = Column(String(100), nullable=False)
    failure_description = Column(Text, nullable=True)
    status_code_received = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    result = Column(Enum(FailureStatus), default=FailureStatus.UNHANDLED)
    error_leaked = Column(Boolean, default=False)
    stack_trace_leaked = Column(Boolean, default=False)
    fix_generated = Column(Boolean, default=False)
    fix_code = Column(Text, nullable=True)
    fix_explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChaosSession", back_populates="failures")
    endpoint = relationship("Endpoint", back_populates="failures")


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chaos_sessions.id"), nullable=False)
    agent = Column(String(50), nullable=False)
    step_type = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    tool_name = Column(String(100), nullable=True)
    tool_input = Column(JSON, nullable=True)
    tool_output = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChaosSession", back_populates="agent_steps")


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chaos_sessions.id"), nullable=False)
    summary = Column(Text, nullable=True)
    critical_findings = Column(JSON, default=list)
    all_findings = Column(JSON, default=list)
    fixes = Column(JSON, default=list)
    risk_score = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChaosSession", back_populates="report")


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chaos_sessions.id"), nullable=False)
    report_id = Column(String, ForeignKey("reports.id"), nullable=False)
    github_repo = Column(String(300), nullable=False)
    branch_name = Column(String(200), nullable=False)
    pr_number = Column(Integer, nullable=True)
    pr_url = Column(String(500), nullable=True)
    pr_title = Column(String(300), nullable=False)
    finding_title = Column(String(300), nullable=True)
    files_changed = Column(JSON, default=list)
    status = Column(String(50), default="opened")
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChaosSession", back_populates="pull_requests")
