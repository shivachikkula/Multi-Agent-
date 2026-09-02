"""Wraps 'Agent-to-Agent Communication' (``core.orchestrator.a2a``) as an
ordinary tool, so an agent can consult another agent as just another
option in its own tool-selection step — no special-casing needed anywhere
in the reasoning loop (``core.agents.base.BaseAgent.run``).
"""
from __future__ import annotations

from typing import Any

from core.orchestrator.a2a import AgentToAgentBus
from core.tools.base import Tool


class AskAgentTool(Tool):
    """One instance per (caller, target) pair — e.g. ``ask_it_support`` lets
    the Finance agent consult the IT Support agent. Keeping the target
    fixed per tool instance (rather than a generic "ask any agent" tool
    with a free-form target parameter) keeps cross-agent calls explicit,
    auditable per agent, and safe from accidentally wiring up a call cycle.
    """

    def __init__(self, bus: AgentToAgentBus, target_agent: str, name: str, description: str) -> None:
        self.name = name
        self.description = description
        self.parameters = {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to ask the other agent."}
            },
            "required": ["question"],
        }
        self._bus = bus
        self._target_agent = target_agent

    async def run(self, question: str, user_id: str = "system", session_id: str = "a2a", **_: Any) -> str:
        return await self._bus.ask(
            to_agent=self._target_agent, question=question, user_id=user_id, session_id=session_id
        )
