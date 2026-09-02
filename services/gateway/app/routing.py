"""'Model Routing & Failover' node inside the AI Gateway box.

Proxies to the primary orchestrator instance and, on connection failure or
a 5xx, retries once against ``ORCHESTRATOR_FAILOVER_URL`` if configured —
the same pattern Azure API Management's backend pool / circuit breaker
policy would give you against multiple Container Apps revisions or
regions.
"""
from __future__ import annotations

import httpx
from fastapi import HTTPException, status

from core.config import Settings


class OrchestratorRouter:
    def __init__(self, settings: Settings) -> None:
        self._primary = settings.orchestrator_base_url.rstrip("/")
        self._failover = (settings.orchestrator_failover_url or "").rstrip("/") or None
        self._client = httpx.AsyncClient(timeout=30)

    async def forward(self, method: str, path: str, **kwargs) -> httpx.Response:
        targets = [self._primary] + ([self._failover] if self._failover else [])
        last_exc: Exception | None = None
        for base_url in targets:
            try:
                response = await self._client.request(method, f"{base_url}{path}", **kwargs)
                if response.status_code < 500:
                    return response
                last_exc = RuntimeError(f"{base_url} returned {response.status_code}")
            except httpx.HTTPError as exc:
                last_exc = exc
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Orchestrator unreachable: {last_exc}")

    async def close(self) -> None:
        await self._client.aclose()
