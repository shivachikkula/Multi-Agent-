"""Long-term memory: durable per-user facts and conversation summaries.

Maps to 'Long Term Memory' under Agent Runtime Services, persisted in the
'SQL Database (Transactional)' box (Postgres locally / Azure SQL in
production via the same SQLAlchemy engine — see ``core.data.sql_store``).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from core.data.sql_store import Base


class LongTermFact(Base):
    __tablename__ = "long_term_facts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LongTermMemory:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def remember(self, user_id: str, key: str, value: str) -> None:
        async with self._session_factory() as session:  # type: AsyncSession
            existing = await session.scalar(
                select(LongTermFact).where(LongTermFact.user_id == user_id, LongTermFact.key == key)
            )
            if existing:
                existing.value = value
                existing.updated_at = datetime.now(timezone.utc)
            else:
                session.add(LongTermFact(user_id=user_id, key=key, value=value))
            await session.commit()

    async def recall(self, user_id: str) -> dict[str, str]:
        async with self._session_factory() as session:
            rows = await session.scalars(select(LongTermFact).where(LongTermFact.user_id == user_id))
            return {row.key: row.value for row in rows}

    async def save_summary(self, session_id: str, user_id: str, summary: str) -> None:
        async with self._session_factory() as session:
            session.add(ConversationSummary(session_id=session_id, user_id=user_id, summary=summary))
            await session.commit()

    async def recent_summaries(self, user_id: str, limit: int = 5) -> list[str]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(ConversationSummary)
                .where(ConversationSummary.user_id == user_id)
                .order_by(ConversationSummary.created_at.desc())
                .limit(limit)
            )
            return [row.summary for row in rows]
