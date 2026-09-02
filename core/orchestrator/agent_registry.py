"""Builds the shared ToolRegistry and the set of available agents, and
does simple keyword-based 'Goal Management' style routing to pick an agent
when the caller doesn't name one explicitly.

Swap ``route`` for an LLM-classification call once a real model is wired
up (Azure OpenAI) if keyword routing isn't precise enough for your domain.
"""
from __future__ import annotations

from core.agents.base import BaseAgent
from core.agents.finance_agent import FinanceAgent
from core.agents.hr_agent import CheckPtoBalanceTool, HRAgent
from core.agents.it_support_agent import ITSupportAgent
from core.agents.sales_agent import LookupLeadTool, SalesAgent
from core.config import Settings
from core.data.sql_store import SqlStore
from core.data.vector_search import VectorSearchIndex
from core.human_in_the_loop.approvals import ApprovalService
from core.llm.base import LLMProvider
from core.tools.calculator_tool import CalculatorTool
from core.tools.finance_tools import CheckBudgetTool, GetExpenseReportTool, SubmitExpenseTool
from core.tools.http_tool import HttpApiTool
from core.tools.it_tools import CheckSystemStatusTool, CreateTicketTool, LookupTicketTool
from core.tools.knowledge_search_tool import KnowledgeSearchTool
from core.tools.registry import ToolRegistry

_ROUTING_KEYWORDS: dict[str, list[str]] = {
    "finance": ["budget", "expense", "reimburs", "invoice", "spend", "cost"],
    "it_support": ["vpn", "password", "ticket", "login", "system", "outage", "laptop", "wifi", "network"],
    "sales": ["lead", "account", "pipeline", "deal", "crm", "prospect"],
    "hr": ["pto", "vacation", "leave", "payroll", "benefits", "onboarding"],
}
DEFAULT_AGENT_ID = "it_support"


async def build_tool_registry(sql: SqlStore, vector_index: VectorSearchIndex, settings: Settings) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(KnowledgeSearchTool(vector_index))
    registry.register(CalculatorTool())
    registry.register(HttpApiTool())
    registry.register(CreateTicketTool(sql))
    registry.register(CheckSystemStatusTool())
    registry.register(LookupTicketTool(sql))
    registry.register(CheckBudgetTool(sql))
    registry.register(SubmitExpenseTool(sql))
    registry.register(GetExpenseReportTool(sql))
    registry.register(LookupLeadTool())
    registry.register(CheckPtoBalanceTool())

    if settings.mcp_server_url:
        from core.tools.mcp_tool import McpToolset

        for mcp_tool in await McpToolset.discover(settings.mcp_server_url):
            registry.register(mcp_tool)

    return registry


def build_agents(
    llm: LLMProvider, tools: ToolRegistry, approvals: ApprovalService, settings: Settings
) -> dict[str, BaseAgent]:
    agents: list[BaseAgent] = [
        ITSupportAgent(llm, tools),
        FinanceAgent(llm, tools, approvals, settings.hitl_finance_approval_threshold_usd),
        SalesAgent(llm, tools),
        HRAgent(llm, tools),
    ]
    return {agent.id: agent for agent in agents}


def route(message: str, agents: dict[str, BaseAgent]) -> str:
    lowered = message.lower()
    for agent_id, keywords in _ROUTING_KEYWORDS.items():
        if agent_id in agents and any(kw in lowered for kw in keywords):
            return agent_id
    return DEFAULT_AGENT_ID if DEFAULT_AGENT_ID in agents else next(iter(agents))
