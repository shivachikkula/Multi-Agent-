from __future__ import annotations

import pytest

from core.agents.it_support_agent import ITSupportAgent
from core.agents.sales_agent import SalesAgent
from core.config import Settings
from core.data.sql_store import SqlStore
from core.human_in_the_loop.approvals import ApprovalService
from core.llm.mock_provider import MockProvider
from core.orchestrator.a2a import AgentToAgentBus
from core.orchestrator.agent_registry import build_agents
from core.schemas import Message
from core.tools.finance_tools import CheckBudgetTool, SubmitExpenseTool
from core.tools.it_tools import CheckSystemStatusTool
from core.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_a2a_bus_routes_question_to_target_agent_and_runs_its_tools():
    tools = ToolRegistry()
    tools.register(CheckSystemStatusTool())
    llm = MockProvider()

    agents = {
        "it_support": ITSupportAgent(llm, tools),
        "sales": SalesAgent(llm, tools),
    }
    bus = AgentToAgentBus(agents)

    answer = await bus.ask(
        to_agent="it_support",
        question="please check system status for the vpn",
        user_id="finance-agent",  # the caller can be another agent, not just a human
        session_id="s1",
    )

    # Proves the *target* agent actually ran (invoked its own tool), not
    # just that some canned string came back.
    assert "vpn" in answer.lower()
    assert "operational" in answer.lower()


@pytest.mark.asyncio
async def test_a2a_bus_derives_a_distinct_session_id_for_the_target_agent():
    captured: dict = {}

    class RecordingAgent(ITSupportAgent):
        async def run(self, messages, *, user_id, session_id):
            captured["user_id"] = user_id
            captured["session_id"] = session_id
            return await super().run(messages, user_id=user_id, session_id=session_id)

    tools = ToolRegistry()
    tools.register(CheckSystemStatusTool())
    bus = AgentToAgentBus({"it_support": RecordingAgent(MockProvider(), tools)})

    await bus.ask(to_agent="it_support", question="hi", user_id="u1", session_id="parent-session")

    # The A2A call must not collide with (or pollute) the parent session's
    # own short-term memory key — it gets its own derived session id.
    assert captured["session_id"] == "parent-session:a2a:it_support"
    assert captured["session_id"] != "parent-session"
    assert captured["user_id"] == "u1"


@pytest.mark.asyncio
async def test_a2a_bus_returns_error_string_for_unknown_agent():
    bus = AgentToAgentBus(agents={})
    answer = await bus.ask(to_agent="nonexistent", question="hi", user_id="u1", session_id="s1")
    assert "Unknown agent" in answer


@pytest.mark.asyncio
async def test_finance_agent_organically_consults_it_support_via_a2a(sql_store: SqlStore):
    """End-to-end proof of the *wired-up* path (not just the bus in
    isolation): a Finance-agent conversation about a system-sounding
    problem makes the Finance agent itself decide to call its
    ``ask_it_support`` tool, which runs the real IT Support agent, which
    runs its own ``check_system_status`` tool — all inside one
    ``FinanceAgent.run()`` turn, exactly as ``build_agents`` wires it for
    the live orchestrator service.
    """
    tools = ToolRegistry()
    tools.register(CheckSystemStatusTool())
    tools.register(CheckBudgetTool(sql_store))
    tools.register(SubmitExpenseTool(sql_store))

    approvals = ApprovalService(sql_store)
    agents, _bus = build_agents(MockProvider(), tools, approvals, Settings())
    finance = agents["finance"]

    result = await finance.run(
        [
            Message(
                role="user",
                content="I think there's a system outage — is the vpn down? asking for it support",
            )
        ],
        user_id="bob",
        session_id="s-finance-a2a",
    )

    assert not result.requires_approval
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "ask_it_support"
    # The nested IT Support agent's own tool call result flows back through.
    assert "operational" in str(result.tool_calls[0].result).lower()
    assert "operational" in result.content.lower()
