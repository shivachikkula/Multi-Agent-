"""Prometheus metrics exposed at ``/metrics`` — feeds 'Alerts &
Notifications' / dashboards. Works standalone (scraped directly) or behind
Azure Monitor's managed Prometheus, which can scrape any /metrics endpoint
from a Container App with no code change here.
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

CHAT_REQUESTS = Counter(
    "agent_chat_requests_total", "Total chat requests handled", ["agent", "status"]
)
CHAT_LATENCY = Histogram("agent_chat_latency_seconds", "Chat request latency", ["agent"])
TOOL_CALLS = Counter("agent_tool_calls_total", "Total tool invocations", ["tool", "status"])
GUARDRAIL_BLOCKS = Counter("agent_guardrail_blocks_total", "Requests blocked by guardrails", ["stage"])
APPROVALS_PENDING = Counter("agent_approvals_created_total", "Human-in-the-loop approvals created", ["agent"])
