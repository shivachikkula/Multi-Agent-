"""Finance agent — the second fully-implemented example agent.

Demonstrates the diagram's Human-in-the-loop path: expenses at or above
``HITL_FINANCE_APPROVAL_THRESHOLD_USD`` are routed to a human approver
instead of being submitted automatically.
"""
from __future__ import annotations

from typing import Any

from core.agents.base import BaseAgent
from core.human_in_the_loop.approvals import ApprovalService
from core.schemas import ApprovalRequest


class FinanceAgent(BaseAgent):
    id = "finance"
    display_name = "Finance Agent"
    description = "Answers budget questions and submits/approves expense reports."
    system_prompt = (
        "You are the Finance agent for an enterprise. Help employees check department budgets "
        "and submit expense reports. Use search_knowledge_base for policy questions. Expenses at "
        "or above the approval threshold will be routed to a human approver automatically — tell "
        "the user that's happening rather than promising immediate reimbursement."
    )
    tool_names = ["search_knowledge_base", "check_budget", "submit_expense", "get_expense_report"]

    def __init__(self, llm, tools, approvals: ApprovalService, threshold_usd: float) -> None:
        super().__init__(llm, tools)
        self._approvals = approvals
        self._threshold = threshold_usd

    async def before_tool_call(
        self, name: str, args: dict[str, Any], *, user_id: str, session_id: str
    ) -> ApprovalRequest | None:
        if name != "submit_expense":
            return None
        amount = float(args.get("amount_usd", 0))
        if amount < self._threshold:
            return None
        request = ApprovalRequest(
            session_id=session_id,
            agent=self.id,
            action="submit_expense",
            payload={**args, "user_id": user_id},
            reason=(
                f"Expense of ${amount:,.2f} is at/above the ${self._threshold:,.2f} "
                "auto-approval threshold and needs finance-manager sign-off."
            ),
        )
        return await self._approvals.create(request)
