"""Deterministic offline LLM stand-in.

Lets the whole platform run end-to-end (agents, tool-calling loop, guardrails,
memory) with zero cloud credentials — useful for local dev, CI, and this
repo's test suite. It performs light intent matching against the available
tools and otherwise echoes a helpful canned reply. Swapped out automatically
for ``AzureOpenAIProvider`` the moment Azure OpenAI credentials are present
(see ``core.llm.factory``).
"""
from __future__ import annotations

import json
import re

from core.llm.base import LLMProvider, LLMResponse, ToolSpec
from core.schemas import Message


class MockProvider(LLMProvider):
    name = "mock"

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        tool_messages = [m for m in messages if m.role == "tool"]
        if tool_messages:
            # A tool has already run this turn — synthesize a final answer
            # from its result instead of calling another tool (keeps the
            # mock provider's reasoning loop convergent).
            summary = "; ".join(f"{m.name} -> {m.content}" for m in tool_messages)
            return LLMResponse(content=f"Done. {summary}")

        last_user = next((m for m in reversed(messages) if m.role == "user"), None)
        text = (last_user.content if last_user else "").strip()
        tool_call = self._match_tool(text, tools or [])
        if tool_call:
            return LLMResponse(content=None, tool_calls=[tool_call])

        system = next((m for m in messages if m.role == "system"), None)
        persona = system.content.splitlines()[0] if system else "assistant"
        reply = (
            f"[mock-llm/{persona[:40]}] I looked at your request but none of my "
            f"available tools matched it directly. You said: \"{text}\". "
            "Set AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY to use a real model."
        )
        return LLMResponse(content=reply)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Cheap, deterministic bag-of-hashed-tokens "embedding" — good enough
        # for local cosine-similarity search without any model download.
        dim = 64
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * dim
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                vec[hash(token) % dim] += 1.0
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            vectors.append([v / norm for v in vec])
        return vectors

    @staticmethod
    def _match_tool(text: str, tools: list[ToolSpec]) -> dict | None:
        if not tools:
            return None
        lowered = text.lower()
        for tool in tools:
            fn = tool.get("function", tool)
            name = fn.get("name", "")
            keywords = name.replace("_", " ").split()
            if any(kw in lowered for kw in keywords if len(kw) > 3):
                args = MockProvider._guess_args(fn, text)
                return {
                    "id": f"call_{name}",
                    "name": name,
                    "arguments": json.dumps(args),
                }
        return None

    #: Known demo values used to pick a plausible argument out of the free-text
    #: request instead of always falling back to the whole message, e.g.
    #: "the VPN is down" -> system="vpn", "travel expense" -> category="travel".
    _KNOWN_SYSTEMS = ("vpn", "email", "identity-portal", "crm")
    _KNOWN_CATEGORIES = ("travel", "airfare", "lodging", "meals", "software", "equipment", "entertainment")

    @staticmethod
    def _guess_args(fn: dict, text: str) -> dict:
        params = fn.get("parameters", {})
        props = params.get("properties", {})
        required = params.get("required", [])
        lowered = text.lower()
        args: dict = {}
        for key, spec in props.items():
            if key in ("query", "question", "text", "description", "subject"):
                args[key] = text
            elif key in ("ticket_id", "id", "expense_id"):
                match = re.search(r"\b([A-Z]{2,}-?\w{2,})\b", text)
                args[key] = match.group(1) if match else "UNKNOWN"
            elif key in ("amount", "amount_usd"):
                match = re.search(r"\$?(\d+(?:\.\d+)?)", text)
                args[key] = float(match.group(1)) if match else 0.0
            elif key == "system":
                args[key] = next((s for s in MockProvider._KNOWN_SYSTEMS if s in lowered), "vpn")
            elif key == "category":
                args[key] = next((c for c in MockProvider._KNOWN_CATEGORIES if c in lowered), "general")
            elif key in ("account", "employee", "department", "expression"):
                args[key] = text
            elif key in required:
                # unknown-but-required param: fall back by JSON type so the
                # tool call doesn't fail with a missing-argument error.
                args[key] = text if spec.get("type") == "string" else 0
        return args
