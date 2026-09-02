"""Template for adding a new "Custom Agent" (right-most box in the
diagram's 'Agents (Examples)' row).

Copy this file, rename the class, fill in the four fields below, register
any new tools it needs in ``core/tools/`` + ``core.orchestrator.agent_registry
.build_tool_registry``, then add an instance to
``core.orchestrator.agent_registry.build_agents``. That's the entire
integration surface — memory, guardrails, gateway routing, and HITL (if you
override ``before_tool_call`` like ``FinanceAgent`` does) all come for free
from ``BaseAgent`` and the orchestrator.
"""
from __future__ import annotations

from core.agents.base import BaseAgent


class CustomAgentTemplate(BaseAgent):
    id = "custom_template"  # unique, url/route-safe id used for routing and logging
    display_name = "Custom Agent"
    description = "Describe what this agent is for."
    system_prompt = "You are a helpful, focused enterprise assistant for <domain>."
    #: Names of tools (from the shared ToolRegistry) this agent may call.
    tool_names: list[str] = ["search_knowledge_base"]
