"""Generic 'Web APIs' connector — lets any agent call an allow-listed HTTP
endpoint. Stands in for the diagram's Web APIs / Custom Connectors box.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from core.tools.base import Tool

# Only http(s) calls to these hosts are permitted — a minimal egress allow-list,
# mirroring what Azure Firewall / a locked-down VNet would enforce in Azure.
DEFAULT_ALLOWED_HOSTS = {"httpbin.org", "api.github.com"}


class HttpApiTool(Tool):
    name = "call_web_api"
    description = "Call an allow-listed external HTTP GET API and return the JSON/text response."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full https:// URL to call."},
        },
        "required": ["url"],
    }

    def __init__(self, allowed_hosts: set[str] | None = None) -> None:
        self._allowed_hosts = allowed_hosts or DEFAULT_ALLOWED_HOSTS

    async def run(self, url: str, **_: Any) -> str:
        host = urlparse(url).hostname or ""
        if host not in self._allowed_hosts:
            return f"Blocked: '{host}' is not on the egress allow-list ({sorted(self._allowed_hosts)})."
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text[:2000]
