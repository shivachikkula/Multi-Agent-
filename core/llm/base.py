"""Provider-agnostic LLM interface — the 'LLM & AI Services' box.

Any concrete provider (Azure OpenAI today; Azure AI Studio / other models
tomorrow) implements this so the orchestrator and agents never depend on a
specific SDK.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.schemas import Message


class ToolSpec(dict):
    """A JSON-schema tool definition in OpenAI/Azure function-calling shape."""


class LLMResponse:
    def __init__(
        self,
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        raw: Any = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls or []
        self.raw = raw


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Single-turn completion, optionally with tool/function calling."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a batch of texts (used by the vector store)."""
