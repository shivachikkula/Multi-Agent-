"""Picks the event bus implementation: Azure Service Bus when configured
(preferred for the worker's durable queue semantics), else the local Redis
Stream so the whole event-driven path works without any Azure resources.
"""
from __future__ import annotations

from core.config import Settings
from core.events.base import EventPublisher


def get_event_bus(settings: Settings) -> EventPublisher:
    if settings.has_service_bus:
        from core.events.service_bus_adapter import ServiceBusEventBus

        return ServiceBusEventBus(settings)

    from core.events.local_queue import RedisEventBus

    return RedisEventBus(settings.redis_url)
