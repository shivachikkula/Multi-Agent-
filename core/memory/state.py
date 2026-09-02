"""Agent run state: the current plan/goal/step for a session.

Maps to 'State Management' under Agent Runtime Services — separate from
short-term chat history so an agent's mid-task progress survives a restart
of the orchestrator process.
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis


class StateStore:
    def __init__(self, redis_url: str) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}:state"

    async def get(self, session_id: str) -> dict[str, Any]:
        raw = await self._redis.get(self._key(session_id))
        return json.loads(raw) if raw else {}

    async def set(self, session_id: str, state: dict[str, Any]) -> None:
        await self._redis.set(self._key(session_id), json.dumps(state), ex=60 * 60 * 6)

    async def update(self, session_id: str, **fields: Any) -> dict[str, Any]:
        state = await self.get(session_id)
        state.update(fields)
        await self.set(session_id, state)
        return state

    async def close(self) -> None:
        await self._redis.aclose()
