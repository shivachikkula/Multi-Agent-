"""Sales agent — lightweight stub from the diagram's 'Agents (Examples)'.

Wired end-to-end into routing/registry/guardrails/memory like the two
flagship agents, but with a single demo tool. Extend it the same way
``it_support_agent.py`` / ``finance_agent.py`` were extended, or use
``template.py`` to start a new agent from scratch.
"""
from __future__ import annotations

from typing import Any

from core.agents.base import BaseAgent
from core.tools.base import Tool

_LEADS = {
    "acme-corp": {"stage": "negotiation", "value_usd": 120_000, "owner": "jane.doe"},
    "globex": {"stage": "discovery", "value_usd": 45_000, "owner": "john.smith"},
}


class LookupLeadTool(Tool):
    name = "lookup_lead"
    description = "Look up a CRM lead/account by name."
    parameters = {"type": "object", "properties": {"account": {"type": "string"}}, "required": ["account"]}

    async def run(self, account: str, **_: Any) -> str:
        lead = _LEADS.get(account.lower().replace(" ", "-"))
        if not lead:
            return f"No lead found for '{account}'."
        return f"{account}: stage={lead['stage']}, value=${lead['value_usd']:,}, owner={lead['owner']}"


class SalesAgent(BaseAgent):
    id = "sales"
    display_name = "Sales Agent"
    description = "Looks up CRM leads/accounts and pipeline status. (stub)"
    system_prompt = (
        "You are the Sales agent. Help with CRM lead/account lookups and general sales "
        "process questions. This is a stub implementation — keep answers brief."
    )
    tool_names = ["search_knowledge_base", "lookup_lead"]
