"""Base class every tool/connector implements — the 'Tools & Connectors
(Agent Actions)' box, covering Web APIs, Azure Functions, Logic Apps,
Power Automate, MCP Servers and Custom Connectors alike behind one
uniform interface the orchestrator's tool-selection step can call.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.llm.base import ToolSpec


class Tool(ABC):
    name: str
    description: str
    #: JSON-schema for arguments, e.g. {"type": "object", "properties": {...}, "required": [...]}
    parameters: dict[str, Any] = {"type": "object", "properties": {}}
    #: True if invoking this tool must go through human-in-the-loop approval first.
    requires_approval: bool = False

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any: ...

    def to_spec(self) -> ToolSpec:
        return ToolSpec(
            {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": self.parameters,
                },
            }
        )
