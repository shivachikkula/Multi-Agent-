"""'Agent-to-Agent Communication' node inside the Agent Orchestrator box.

Lets one agent consult another synchronously within the same turn (e.g. the
Finance agent asking the IT Support agent whether the expense portal is up)
without either agent knowing about routing, memory, or guardrails — the bus
just runs the target agent and hands back its final text.
"""
from __future__ import annotations

from core.agents.base import BaseAgent
from core.schemas import Message


class AgentToAgentBus:
    def __init__(self, agents: dict[str, BaseAgent]) -> None:
        self._agents = agents

    async def ask(self, *, to_agent: str, question: str, user_id: str, session_id: str) -> str:
        agent = self._agents.get(to_agent)
        if agent is None:
            return f"Unknown agent '{to_agent}'."
        result = await agent.run(
            [Message(role="user", content=question)],
            user_id=user_id,
            session_id=f"{session_id}:a2a:{to_agent}",
        )
        return result.content
