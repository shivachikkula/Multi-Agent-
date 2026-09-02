"""Local stand-in for Event Hub / Service Bus, built on Redis Pub/Sub +
Streams so the async-processing path (used by the worker service and by
the orchestrator's HITL notifications) works with no Azure resources.

A Redis Stream (not plain pub/sub) is used so events survive a worker
restart between publish and consume, the same durability guarantee Event
Hub/Service Bus provide.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import redis.asyncio as redis

from core.events.base import EventConsumer, EventPublisher
from core.schemas import AgentEvent

_STREAM = "agent-events"
_GROUP = "agent-workers"


class RedisEventBus(EventPublisher, EventConsumer):
    def __init__(self, redis_url: str, consumer_name: str = "worker-1") -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._consumer_name = consumer_name

    async def _ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(_STREAM, _GROUP, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, event: AgentEvent) -> None:
        await self._redis.xadd(_STREAM, {"data": event.model_dump_json()})

    async def consume(self) -> AsyncIterator[AgentEvent]:
        await self._ensure_group()
        while True:
            entries = await self._redis.xreadgroup(
                _GROUP, self._consumer_name, {_STREAM: ">"}, count=10, block=5000
            )
            for _stream, messages in entries:
                for message_id, fields in messages:
                    yield AgentEvent.model_validate_json(fields["data"])
                    await self._redis.xack(_STREAM, _GROUP, message_id)

    async def close(self) -> None:
        await self._redis.aclose()
