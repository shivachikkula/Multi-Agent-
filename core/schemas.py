"""Shared Pydantic models passed between gateway, orchestrator and worker."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return uuid.uuid4().hex


class ChatRequest(BaseModel):
    session_id: str | None = None
    user_id: str = "anonymous"
    message: str
    agent: str | None = Field(
        default=None, description="Force routing to a specific agent id; omit for auto-routing."
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None


class GuardrailVerdict(BaseModel):
    allowed: bool
    category: str | None = None
    reason: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    agent: str
    reply: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    guardrail: GuardrailVerdict | None = None
    requires_approval: bool = False
    approval_id: str | None = None
    trace_id: str | None = None


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=_id)
    session_id: str
    agent: str
    action: str
    payload: dict[str, Any]
    reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=_now)
    decided_at: datetime | None = None
    decided_by: str | None = None


class AgentEvent(BaseModel):
    """Envelope published onto the async event bus (Event Hub / Service Bus stand-in)."""

    id: str = Field(default_factory=_id)
    type: str
    source_agent: str
    session_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
