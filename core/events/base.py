"""'Event & Async Processing' box — common interface implemented by the
local Redis queue, Azure Event Hub, and Azure Service Bus adapters.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from core.schemas import AgentEvent


class EventPublisher(ABC):
    @abstractmethod
    async def publish(self, event: AgentEvent) -> None: ...


class EventConsumer(ABC):
    @abstractmethod
    def consume(self) -> AsyncIterator[AgentEvent]: ...
