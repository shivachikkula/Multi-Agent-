from __future__ import annotations

import pytest

from core.data.sql_store import SqlStore
from core.tools.calculator_tool import CalculatorTool
from core.tools.finance_tools import CheckBudgetTool, SubmitExpenseTool
from core.tools.it_tools import CheckSystemStatusTool, CreateTicketTool, LookupTicketTool
from core.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_calculator_tool_evaluates_expression():
    result = await CalculatorTool().run(expression="1000 * 0.15 + 42")
    assert result == 192.0


@pytest.mark.asyncio
async def test_calculator_tool_rejects_unsafe_expression():
    with pytest.raises(Exception):
        await CalculatorTool().run(expression="__import__('os').system('echo pwned')")


@pytest.mark.asyncio
async def test_check_system_status_known_and_unknown():
    tool = CheckSystemStatusTool()
    assert "operational" in await tool.run(system="vpn")
    assert "Unknown system" in await tool.run(system="mainframe")


@pytest.mark.asyncio
async def test_create_and_lookup_ticket_roundtrip(sql_store: SqlStore):
    create = CreateTicketTool(sql_store)
    lookup = LookupTicketTool(sql_store)

    created_msg = await create.run(subject="VPN broken", description="Can't connect", user_id="alice")
    ticket_id = created_msg.split()[2]  # "Created ticket <ID> (status: open)."

    found = await lookup.run(ticket_id=ticket_id)
    assert "VPN broken" in found
    assert "open" in found

    missing = await lookup.run(ticket_id="IT-DOESNOTEXIST")
    assert "No ticket found" in missing


@pytest.mark.asyncio
async def test_check_budget_and_submit_expense(sql_store: SqlStore):
    await sql_store.seed_demo_data()
    budget_tool = CheckBudgetTool(sql_store)
    result = await budget_tool.run(department="Engineering", fiscal_year="FY26")
    assert "Engineering" in result
    assert "remaining" in result

    submit_tool = SubmitExpenseTool(sql_store)
    receipt = await submit_tool.run(category="travel", amount_usd=250.0, user_id="bob")
    assert "approved" in receipt


def test_tool_registry_specs_filtering():
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(CheckSystemStatusTool())

    all_specs = registry.specs()
    assert len(all_specs) == 2

    filtered = registry.specs(["calculate"])
    assert len(filtered) == 1
    assert filtered[0]["function"]["name"] == "calculate"

    assert "calculate" in registry
    assert "nonexistent_tool" not in registry
