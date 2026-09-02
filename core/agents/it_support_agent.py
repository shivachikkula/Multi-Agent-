"""IT Support agent — one of the two fully-implemented example agents."""
from __future__ import annotations

from core.agents.base import BaseAgent


class ITSupportAgent(BaseAgent):
    id = "it_support"
    display_name = "IT Support Agent"
    description = "Troubleshoots systems, checks status, and files support tickets."
    system_prompt = (
        "You are the IT Support agent for an enterprise. Help employees troubleshoot issues, "
        "check system status, and file tickets. Use search_knowledge_base for policy/runbook "
        "questions before answering from memory. Only escalate identity/security-sensitive "
        "actions (like password resets after a suspected compromise) — never claim to have "
        "reset a password yourself, direct the user to the self-service portal or file a "
        "ticket instead."
    )
    tool_names = [
        "search_knowledge_base",
        "check_system_status",
        "create_support_ticket",
        "lookup_ticket",
    ]
