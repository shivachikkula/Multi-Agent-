from __future__ import annotations

import httpx
import pytest
from fakeredis import aioredis as fakeredis_aioredis

from services.gateway.app import main as gateway_main


class _FakeOrchestratorResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeRouter:
    """Stands in for OrchestratorRouter so gateway tests don't need a real
    orchestrator process — only the gateway's own auth/rate-limit/proxy
    behavior is under test here."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def forward(self, method: str, path: str, **kwargs):
        self.calls.append((method, path))
        return _FakeOrchestratorResponse(200, {"echo": path})

    async def close(self) -> None:
        pass


@pytest.fixture
async def client():
    gateway_main.settings.gateway_rate_limit_per_minute = 3
    limiter = gateway_main.RateLimiter(gateway_main.settings.redis_url, 3)
    limiter._redis = fakeredis_aioredis.FakeRedis(decode_responses=True)

    gateway_main.app.state.rate_limiter = limiter
    gateway_main.app.state.router = _FakeRouter()

    transport = httpx.ASGITransport(app=gateway_main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_missing_auth_is_rejected(client: httpx.AsyncClient):
    resp = await client.get("/v1/agents")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_valid_api_key_is_forwarded(client: httpx.AsyncClient):
    resp = await client.get("/v1/agents", headers={"X-API-Key": "dev-local-key"})
    assert resp.status_code == 200
    assert resp.json() == {"echo": "/agents"}


@pytest.mark.asyncio
async def test_invalid_api_key_is_rejected(client: httpx.AsyncClient):
    resp = await client.get("/v1/agents", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_oversized_message_rejected_before_forwarding(client: httpx.AsyncClient):
    resp = await client.post(
        "/v1/chat",
        headers={"X-API-Key": "dev-local-key"},
        json={"message": "x" * (gateway_main.MAX_MESSAGE_CHARS + 1)},
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_rate_limit_enforced_per_key(client: httpx.AsyncClient):
    headers = {"X-API-Key": "dev-local-key"}
    for _ in range(3):
        resp = await client.get("/v1/agents", headers=headers)
        assert resp.status_code == 200
    resp = await client.get("/v1/agents", headers=headers)
    assert resp.status_code == 429
