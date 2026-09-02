"""'SQL Database (Transactional)' box — Postgres locally, Azure SQL/Postgres
Flexible Server in production via the same async SQLAlchemy engine (swap
``SQL_DATABASE_URL``).

Also home to the domain tables the two flagship agents use directly:
IT support tickets and finance expense reports.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Ticket(Base):
    __tablename__ = "it_tickets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128))
    subject: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ExpenseReport(Base):
    __tablename__ = "expense_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64))
    amount_usd: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="submitted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Budget(Base):
    __tablename__ = "budgets"

    department: Mapped[str] = mapped_column(String(64), primary_key=True)
    fiscal_year: Mapped[str] = mapped_column(String(8), primary_key=True)
    allocated_usd: Mapped[float] = mapped_column(Float)
    spent_usd: Mapped[float] = mapped_column(Float, default=0.0)


class SqlStore:
    """Thin async engine/session wrapper shared by every SQL-backed adapter."""

    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init_models(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def seed_demo_data(self) -> None:
        async with self.session_factory() as session:  # type: AsyncSession
            from sqlalchemy import select

            existing = await session.scalar(select(Budget).limit(1))
            if existing:
                return
            session.add_all(
                [
                    Budget(department="Engineering", fiscal_year="FY26", allocated_usd=500_000, spent_usd=210_000),
                    Budget(department="Sales", fiscal_year="FY26", allocated_usd=300_000, spent_usd=145_000),
                    Budget(department="IT", fiscal_year="FY26", allocated_usd=150_000, spent_usd=98_000),
                ]
            )
            await session.commit()

    async def dispose(self) -> None:
        await self.engine.dispose()
