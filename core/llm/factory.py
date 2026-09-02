"""Selects an LLM provider based on configured credentials.

Azure OpenAI is the default per the reference architecture; when no
credentials are configured we fall back to the offline mock so the rest of
the platform is still fully runnable and testable.
"""
from __future__ import annotations

from core.config import Settings, get_settings
from core.llm.base import LLMProvider

_provider: LLMProvider | None = None


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    global _provider
    if _provider is not None:
        return _provider

    settings = settings or get_settings()
    if settings.has_azure_openai:
        from core.llm.azure_openai_provider import AzureOpenAIProvider

        _provider = AzureOpenAIProvider(settings)
    else:
        from core.llm.mock_provider import MockProvider

        _provider = MockProvider()
    return _provider
