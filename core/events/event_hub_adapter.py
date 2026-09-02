"""'Azure Event Hub' adapter — high-throughput event ingestion (e.g.
telemetry, audit trail fan-out). Used for publish-only, fire-and-forget
event streams; see ``service_bus_adapter.py`` for the queue with a
consumer group used by the worker service.
"""
from __future__ import annotations

from core.config import Settings
from core.events.base import EventPublisher
from core.schemas import AgentEvent


class EventHubPublisher(EventPublisher):
    def __init__(self, settings: Settings) -> None:
        from azure.eventhub.aio import EventHubProducerClient

        self._client = EventHubProducerClient.from_connection_string(settings.event_hub_connection_string)

    async def publish(self, event: AgentEvent) -> None:
        from azure.eventhub import EventData

        async with self._client:
            batch = await self._client.create_batch()
            batch.add(EventData(event.model_dump_json()))
            await self._client.send_batch(batch)
