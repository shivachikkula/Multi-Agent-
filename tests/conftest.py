from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.data.sql_store import Base, SqlStore


@pytest_asyncio.fixture
async def sql_store() -> SqlStore:
    """An in-memory SQLite-backed SqlStore for fast, isolated tests — the
    same schema Postgres uses in docker-compose, minus the Postgres-only
    ``created_at`` timezone handling exercised separately in the smoke test.
    """
    store = SqlStore.__new__(SqlStore)
    store.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    store.session_factory = async_sessionmaker(store.engine, expire_on_commit=False)
    async with store.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield store
    await store.engine.dispose()
