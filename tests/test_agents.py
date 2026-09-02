from __future__ import annotations

import pytest

from core.agents.finance_agent import FinanceAgent
from core.agents.it_support_agent import ITSupportAgent
from core.data.sql_store import SqlStore
from core.human_in_the_loop.approvals import ApprovalService
from core.llm.mock_provider import MockProvider
from core.schemas import Message
from core.tools.finance_tools import CheckBudgetTool, SubmitExpenseTool
from core.tools.it_tools import CheckSystemStatusTool, CreateTicketTool
from core.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_it_support_agent_calls_tool_and_converges(sql_store: SqlStore):
    registry = ToolRegistry()
    registry.register(CheckSystemStatusTool())
    registry.register(CreateTicketTool(sql_store))
    agent = ITSupportAgent(MockProvider(), registry)

    result = await agent.run(
        [Message(role="user", content="Please check system status for the vpn")],
        user_id="alice",
        session_id="s1",
    )

    assert not result.requires_approval
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "check_system_status"
    assert "operational" in result.content


@pytest.mark.asyncio
async def test_finance_agent_auto_approves_small_expense(sql_store: SqlStore):
    await sql_store.seed_demo_data()
    registry = ToolRegistry()
    registry.register(CheckBudgetTool(sql_store))
    registry.register(SubmitExpenseTool(sql_store))
    approvals = ApprovalService(sql_store)
    agent = FinanceAgent(MockProvider(), registry, approvals, threshold_usd=1000.0)

    result = await agent.run(
        [Message(role="user", content="Submit a travel expense report for $200")],
        user_id="bob",
        session_id="s2",
    )

    assert not result.requires_approval
    assert result.tool_calls[0].name == "submit_expense"
    assert "approved" in result.content
    assert not await approvals.list_pending()


@pytest.mark.asyncio
async def test_finance_agent_routes_large_expense_to_hitl(sql_store: SqlStore):
    await sql_store.seed_demo_data()
    registry = ToolRegistry()
    registry.register(CheckBudgetTool(sql_store))
    registry.register(SubmitExpenseTool(sql_store))
    approvals = ApprovalService(sql_store)
    agent = FinanceAgent(MockProvider(), registry, approvals, threshold_usd=1000.0)

    result = await agent.run(
        [Message(role="user", content="Submit a travel expense report for $5000")],
        user_id="bob",
        session_id="s3",
    )

    assert result.requires_approval
    assert result.approval is not None
    assert result.approval.action == "submit_expense"
    assert result.approval.payload["amount_usd"] == 5000.0

    pending = await approvals.list_pending()
    assert len(pending) == 1
    assert pending[0].id == result.approval.id
