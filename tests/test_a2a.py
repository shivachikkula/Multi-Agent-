from __future__ import annotations

import pytest

from core.agents.it_support_agent import ITSupportAgent
from core.agents.sales_agent import SalesAgent
from core.llm.mock_provider import MockProvider
from core.orchestrator.a2a import AgentToAgentBus
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
