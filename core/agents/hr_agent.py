"""HR agent — lightweight stub from the diagram's 'Agents (Examples)'.

See the note in ``sales_agent.py`` — same pattern, one demo tool.
"""
from __future__ import annotations

from typing import Any

from core.agents.base import BaseAgent
from core.tools.base import Tool

_PTO_BALANCES = {
    "alice": 12.5,
    "bob": 4.0,
}


class CheckPtoBalanceTool(Tool):
    name = "check_pto_balance"
    description = "Check an employee's remaining PTO balance in days."
    parameters = {"type": "object", "properties": {"employee": {"type": "string"}}, "required": ["employee"]}

    async def run(self, employee: str, **_: Any) -> str:
        balance = _PTO_BALANCES.get(employee.lower())
        if balance is None:
            return f"No PTO record found for '{employee}'."
        return f"{employee} has {balance} PTO days remaining."


class HRAgent(BaseAgent):
    id = "hr"
    display_name = "HR Agent"
    description = "Answers PTO balance and general HR policy questions. (stub)"
    system_prompt = (
        "You are the HR agent. Help with PTO balance lookups and general HR policy questions. "
        "This is a stub implementation — keep answers brief and never disclose one employee's "
        "PTO balance to another user."
    )
    tool_names = ["search_knowledge_base", "check_pto_balance"]
