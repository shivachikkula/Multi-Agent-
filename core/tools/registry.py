"""Tool registry: name -> Tool lookup used by the orchestrator's tool-
selection step and exposed to the LLM as function-calling specs."""
from __future__ import annotations

from core.llm.base import ToolSpec
from core.tools.base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self, names: list[str] | None = None) -> list[ToolSpec]:
        tools = self._tools.values() if names is None else (self._tools[n] for n in names if n in self._tools)
        return [t.to_spec() for t in tools]

    def __contains__(self, name: str) -> bool:
        return name in self._tools
