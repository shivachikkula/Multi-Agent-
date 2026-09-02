from __future__ import annotations

from core.agents.finance_agent import FinanceAgent
from core.agents.hr_agent import HRAgent
from core.agents.it_support_agent import ITSupportAgent
from core.agents.sales_agent import SalesAgent
from core.llm.mock_provider import MockProvider
from core.orchestrator.agent_registry import route
from core.tools.registry import ToolRegistry


def _agents():
    llm, tools = MockProvider(), ToolRegistry()
    return {
        "it_support": ITSupportAgent(llm, tools),
        "finance": FinanceAgent(llm, tools, approvals=None, threshold_usd=1000.0),
        "sales": SalesAgent(llm, tools),
        "hr": HRAgent(llm, tools),
    }


def test_route_finance_keywords():
    assert route("what's my remaining budget this quarter?", _agents()) == "finance"


def test_route_it_keywords():
    assert route("my vpn keeps disconnecting", _agents()) == "it_support"


def test_route_sales_keywords():
    assert route("what stage is the acme-corp lead in?", _agents()) == "sales"


def test_route_hr_keywords():
    assert route("how much pto do I have left?", _agents()) == "hr"


def test_route_falls_back_to_default_agent():
    assert route("hello there, general question", _agents()) == "it_support"
