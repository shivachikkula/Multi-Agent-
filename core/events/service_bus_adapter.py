"""'Azure Service Bus' adapter — the durable task queue the worker service
drains, matching the local Redis Stream's publish/consume contract.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from core.config import Settings
from core.events.base import EventConsumer, EventPublisher
from core.schemas import AgentEvent


class ServiceBusEventBus(EventPublisher, EventConsumer):
    def __init__(self, settings: Settings) -> None:
        from azure.servicebus.aio import ServiceBusClient

        self._client = ServiceBusClient.from_connection_string(settings.service_bus_connection_string)
        self._queue_name = settings.service_bus_queue

    async def publish(self, event: AgentEvent) -> None:
        from azure.servicebus import ServiceBusMessage

        async with self._client.get_queue_sender(self._queue_name) as sender:
            await sender.send_messages(ServiceBusMessage(event.model_dump_json()))

    async def consume(self) -> AsyncIterator[AgentEvent]:
        async with self._client.get_queue_receiver(self._queue_name) as receiver:
            async for msg in receiver:
                yield AgentEvent.model_validate_json(str(msg))
                await receiver.complete_message(msg)
