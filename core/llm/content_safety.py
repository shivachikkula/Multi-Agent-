"""Azure AI Content Safety adapter, with a local heuristic fallback.

Backs the 'Guardrails & Safety' node inside the orchestrator and the
'Azure Content Safety & Guardrails' box under LLM & AI Services.
"""
from __future__ import annotations

import re

from core.config import Settings

_BLOCKLIST = (
    "ignore previous instructions",
    "reveal your system prompt",
    "how to build a bomb",
    "credit card number",
    "social security number",
)


class ContentSafetyResult:
    def __init__(self, flagged: bool, category: str | None = None, reason: str | None = None) -> None:
        self.flagged = flagged
        self.category = category
        self.reason = reason


class ContentSafetyChecker:
    """Interface implemented by both the Azure-backed and local checkers."""

    async def check(self, text: str) -> ContentSafetyResult:  # pragma: no cover - interface
        raise NotImplementedError


class LocalHeuristicChecker(ContentSafetyChecker):
    """Regex/keyword based guardrail used when Azure AI Content Safety isn't configured."""

    async def check(self, text: str) -> ContentSafetyResult:
        lowered = text.lower()
        for phrase in _BLOCKLIST:
            if phrase in lowered:
                return ContentSafetyResult(True, category="blocklist", reason=f"matched '{phrase}'")
        if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text):
            return ContentSafetyResult(True, category="pii", reason="looks like a US SSN")
        if re.search(r"\b(?:\d[ -]*?){13,16}\b", text):
            return ContentSafetyResult(True, category="pii", reason="looks like a card number")
        return ContentSafetyResult(False)


class AzureContentSafetyChecker(ContentSafetyChecker):
    def __init__(self, settings: Settings) -> None:
        from azure.ai.contentsafety.aio import ContentSafetyClient
        from azure.core.credentials import AzureKeyCredential

        self._client = ContentSafetyClient(
            settings.azure_content_safety_endpoint,
            AzureKeyCredential(settings.azure_content_safety_api_key),
        )

    async def check(self, text: str) -> ContentSafetyResult:
        from azure.ai.contentsafety.models import AnalyzeTextOptions

        result = await self._client.analyze_text(AnalyzeTextOptions(text=text))
        for category_result in result.categories_analysis:
            if category_result.severity and category_result.severity >= 4:
                return ContentSafetyResult(
                    True,
                    category=category_result.category,
                    reason=f"severity {category_result.severity}",
                )
        return ContentSafetyResult(False)


def get_content_safety_checker(settings: Settings) -> ContentSafetyChecker:
    if settings.has_content_safety:
        return AzureContentSafetyChecker(settings)
    return LocalHeuristicChecker()
