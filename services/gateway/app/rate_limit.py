"""'Rate Limiting & Quotas' node inside the AI Gateway box.

A fixed 60s-window counter per principal, stored in Redis so it's shared
across every gateway replica — the same behavior Azure API Management's
rate-limit policy gives you for free, reimplemented here since we're not
running actual APIM.
"""
from __future__ import annotations

import time

import redis.asyncio as redis
from fastapi import HTTPException, status


class RateLimiter:
    def __init__(self, redis_url: str, limit_per_minute: int) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._limit = limit_per_minute

    async def enforce(self, principal_key: str) -> None:
        window = int(time.time() // 60)
        key = f"ratelimit:{principal_key}:{window}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 60)
        if count > self._limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Rate limit exceeded ({self._limit}/min). Try again shortly.",
            )

    async def close(self) -> None:
        await self._redis.aclose()
