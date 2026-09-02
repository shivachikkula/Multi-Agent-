"""'MCP Servers' box under Tools & Connectors.

Wraps an external Model Context Protocol server's tools so an agent can call
them like any other local tool. Requires the optional ``mcp`` package and a
running MCP server; disabled (not registered) unless ``MCP_SERVER_URL`` is
configured — see ``core.orchestrator.agent_registry``.
"""
from __future__ import annotations

from typing import Any

from core.tools.base import Tool


class McpTool(Tool):
    """Proxies a single remote MCP tool as a local ``Tool``.

    One instance is created per remote tool discovered via
    ``McpToolset.discover`` so each keeps the remote tool's own name,
    description and JSON schema for the orchestrator's tool-selection step.
    """

    def __init__(self, server_url: str, remote_name: str, description: str, parameters: dict) -> None:
        self.name = f"mcp__{remote_name}"
        self.description = f"[MCP:{server_url}] {description}"
        self.parameters = parameters
        self._server_url = server_url
        self._remote_name = remote_name

    async def run(self, **kwargs: Any) -> Any:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        async with sse_client(self._server_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(self._remote_name, kwargs)
                return "\n".join(getattr(c, "text", str(c)) for c in result.content)


class McpToolset:
    @staticmethod
    async def discover(server_url: str) -> list[McpTool]:
        """Connects to an MCP server once at startup and returns a ``McpTool``
        wrapper per tool it advertises. Returns [] if the server is
        unreachable so a misconfigured MCP endpoint never blocks boot."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            async with sse_client(server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    return [
                        McpTool(
                            server_url=server_url,
                            remote_name=t.name,
                            description=t.description or "",
                            parameters=t.inputSchema or {"type": "object", "properties": {}},
                        )
                        for t in tools.tools
                    ]
        except Exception:
            return []
