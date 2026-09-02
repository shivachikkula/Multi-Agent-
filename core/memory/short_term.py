"""Short-term (conversation window) memory, backed by Redis.

Maps to 'Short Term Memory' under Agent Runtime Services. Redis also stands
in for the low-latency session cache an Azure Cache for Redis instance
would provide in production.
"""
from __future__ import annotations

import json

import redis.asyncio as redis

from core.schemas import Message

_TTL_SECONDS = 60 * 60 * 6  # 6h conversation window
_MAX_TURNS = 20


class ShortTermMemory:
    def __init__(self, redis_url: str) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}:messages"

    async def append(self, session_id: str, message: Message) -> None:
        key = self._key(session_id)
        await self._redis.rpush(key, message.model_dump_json())
        await self._redis.ltrim(key, -_MAX_TURNS, -1)
        await self._redis.expire(key, _TTL_SECONDS)

    async def get_history(self, session_id: str) -> list[Message]:
        raw = await self._redis.lrange(self._key(session_id), 0, -1)
        return [Message(**json.loads(r)) for r in raw]

    async def clear(self, session_id: str) -> None:
        await self._redis.delete(self._key(session_id))

    async def close(self) -> None:
        await self._redis.aclose()
