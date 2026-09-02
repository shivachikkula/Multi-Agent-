"""Azure OpenAI Service adapter — 'LLM & AI Services' box in the diagram.

Uses API-key auth by default; set ``AZURE_USE_MANAGED_IDENTITY=true`` (and
leave AZURE_OPENAI_API_KEY unset) to authenticate via Managed Identity /
Entra ID instead, matching the 'Managed Identity (for Agents & Services)'
box.
"""
from __future__ import annotations

from core.config import Settings, env_flag
from core.llm.base import LLMProvider, LLMResponse, ToolSpec
from core.schemas import Message


class AzureOpenAIProvider(LLMProvider):
    name = "azure_openai"

    def __init__(self, settings: Settings) -> None:
        from openai import AsyncAzureOpenAI  # imported lazily: optional dep

        self.deployment = settings.azure_openai_deployment
        self.embedding_deployment = f"{settings.azure_openai_deployment}-embedding"

        if env_flag("AZURE_USE_MANAGED_IDENTITY") and not settings.azure_openai_api_key:
            from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            self.client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version=settings.azure_openai_api_version,
            )
        else:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        payload = [
            {"role": m.role, "content": m.content, **({"name": m.name} if m.name else {})}
            for m in messages
        ]
        kwargs: dict = {"model": self.deployment, "messages": payload, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        completion = await self.client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        tool_calls = [
            {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
            for tc in (choice.message.tool_calls or [])
        ]
        return LLMResponse(content=choice.message.content, tool_calls=tool_calls, raw=completion)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result = await self.client.embeddings.create(model=self.embedding_deployment, input=texts)
        return [d.embedding for d in result.data]
