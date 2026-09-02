"""'Guardrails & Safety' node inside the Agent Orchestrator box.

Checked on both the inbound user message and the agent's outbound reply,
using whichever ``ContentSafetyChecker`` is active (Azure AI Content Safety
or the local heuristic fallback — see ``core.llm.content_safety``).
"""
from __future__ import annotations

from core.llm.content_safety import ContentSafetyChecker
from core.schemas import GuardrailVerdict


class GuardrailsEngine:
    def __init__(self, checker: ContentSafetyChecker) -> None:
        self._checker = checker

    async def check(self, text: str) -> GuardrailVerdict:
        result = await self._checker.check(text)
        if result.flagged:
            return GuardrailVerdict(allowed=False, category=result.category, reason=result.reason)
        return GuardrailVerdict(allowed=True)
