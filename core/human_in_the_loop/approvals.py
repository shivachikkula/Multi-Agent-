"""'Human in the Loop' box: approvals, reviews & escalations.

Sensitive agent actions are queued here instead of executed immediately.
A reviewer approves/rejects via the orchestrator's ``/approvals`` API (or
the static reviewer UI); on approval the orchestrator (or worker, for
actions submitted asynchronously) actually performs the pending tool call
and publishes an ``AgentEvent`` so any listener can react.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from core.data.sql_store import Base, SqlStore
from core.schemas import ApprovalRequest, ApprovalStatus


class ApprovalRecord(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64))
    agent: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(16), default=ApprovalStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)


def _to_model(row: ApprovalRecord) -> ApprovalRequest:
    return ApprovalRequest(
        id=row.id,
        session_id=row.session_id,
        agent=row.agent,
        action=row.action,
        payload=row.payload,
        reason=row.reason,
        status=ApprovalStatus(row.status),
        created_at=row.created_at,
        decided_at=row.decided_at,
        decided_by=row.decided_by,
    )


class ApprovalService:
    def __init__(self, sql: SqlStore) -> None:
        self._sql = sql

    async def create(self, request: ApprovalRequest) -> ApprovalRequest:
        async with self._sql.session_factory() as session:
            session.add(
                ApprovalRecord(
                    id=request.id,
                    session_id=request.session_id,
                    agent=request.agent,
                    action=request.action,
                    payload=request.payload,
                    reason=request.reason,
                    status=request.status.value,
                    created_at=request.created_at,
                )
            )
            await session.commit()
        return request

    async def get(self, approval_id: str) -> ApprovalRequest | None:
        async with self._sql.session_factory() as session:
            row = await session.get(ApprovalRecord, approval_id)
            return _to_model(row) if row else None

    async def list_pending(self) -> list[ApprovalRequest]:
        async with self._sql.session_factory() as session:
            rows = await session.scalars(
                select(ApprovalRecord).where(ApprovalRecord.status == ApprovalStatus.PENDING.value)
            )
            return [_to_model(r) for r in rows]

    async def decide(self, approval_id: str, approved: bool, decided_by: str) -> ApprovalRequest | None:
        async with self._sql.session_factory() as session:
            row = await session.get(ApprovalRecord, approval_id)
            if not row:
                return None
            row.status = ApprovalStatus.APPROVED.value if approved else ApprovalStatus.REJECTED.value
            row.decided_at = datetime.now(timezone.utc)
            row.decided_by = decided_by
            await session.commit()
            return _to_model(row)
