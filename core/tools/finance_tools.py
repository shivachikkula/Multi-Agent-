"""Tools used by the Finance agent. ``submit_expense`` is the one action in
this whole app gated by Human-in-the-loop: the agent (see
``core.agents.finance_agent``) decides whether an amount needs approval and
either calls this tool directly or routes through
``core.human_in_the_loop.approvals`` first.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from core.data.sql_store import Budget, ExpenseReport, SqlStore
from core.tools.base import Tool


class CheckBudgetTool(Tool):
    name = "check_budget"
    description = "Check remaining budget for a department in a fiscal year."
    parameters = {
        "type": "object",
        "properties": {
            "department": {"type": "string"},
            "fiscal_year": {"type": "string", "description": "e.g. FY26"},
        },
        "required": ["department"],
    }

    def __init__(self, sql: SqlStore) -> None:
        self._sql = sql

    async def run(self, department: str, fiscal_year: str = "FY26", **_: Any) -> str:
        async with self._sql.session_factory() as session:
            budget = await session.scalar(
                select(Budget).where(Budget.department == department, Budget.fiscal_year == fiscal_year)
            )
        if not budget:
            return f"No budget record for {department} in {fiscal_year}."
        remaining = budget.allocated_usd - budget.spent_usd
        return (
            f"{department} {fiscal_year}: allocated ${budget.allocated_usd:,.0f}, "
            f"spent ${budget.spent_usd:,.0f}, remaining ${remaining:,.0f}."
        )


class SubmitExpenseTool(Tool):
    name = "submit_expense"
    description = "Submit (persist) an approved expense report."
    parameters = {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "amount_usd": {"type": "number"},
        },
        "required": ["category", "amount_usd"],
    }

    def __init__(self, sql: SqlStore) -> None:
        self._sql = sql

    async def run(self, category: str, amount_usd: float, user_id: str = "anonymous", **_: Any) -> str:
        expense_id = f"EXP-{uuid.uuid4().hex[:6].upper()}"
        async with self._sql.session_factory() as session:
            session.add(
                ExpenseReport(
                    id=expense_id,
                    user_id=user_id,
                    category=category,
                    amount_usd=amount_usd,
                    status="approved",
                )
            )
            await session.commit()
        return f"Recorded expense {expense_id}: {category} ${amount_usd:,.2f} (status: approved)."


class GetExpenseReportTool(Tool):
    name = "get_expense_report"
    description = "Look up a previously submitted expense report by id."
    parameters = {
        "type": "object",
        "properties": {"expense_id": {"type": "string"}},
        "required": ["expense_id"],
    }

    def __init__(self, sql: SqlStore) -> None:
        self._sql = sql

    async def run(self, expense_id: str, **_: Any) -> str:
        async with self._sql.session_factory() as session:
            expense = await session.scalar(select(ExpenseReport).where(ExpenseReport.id == expense_id))
        if not expense:
            return f"No expense report found with id {expense_id}."
        return f"{expense.id}: {expense.category} ${expense.amount_usd:,.2f} — status: {expense.status}"
