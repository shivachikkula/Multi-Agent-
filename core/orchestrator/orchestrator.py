"""The Agent Orchestrator: ties planning/tool-selection (in each
``BaseAgent``), memory, guardrails, goal management, and async eventing
into the single entry point the orchestrator service's ``/chat`` route
calls. This is the runtime heart of the 'Agent Orchestration Layer' box.
"""
from __future__ import annotations

import uuid

from core.agents.base import BaseAgent
from core.events.base import EventPublisher
from core.memory.long_term import LongTermMemory
from core.memory.short_term import ShortTermMemory
from core.orchestrator.agent_registry import route
from core.orchestrator.goal_management import GoalManager
from core.orchestrator.guardrails import GuardrailsEngine
from core.schemas import AgentEvent, ChatRequest, ChatResponse, Message


class Orchestrator:
    def __init__(
        self,
        agents: dict[str, BaseAgent],
        short_term: ShortTermMemory,
        long_term: LongTermMemory,
        goals: GoalManager,
        guardrails: GuardrailsEngine,
        events: EventPublisher,
    ) -> None:
        self._agents = agents
        self._short_term = short_term
        self._long_term = long_term
        self._goals = goals
        self._guardrails = guardrails
        self._events = events

    @property
    def agents(self) -> dict[str, BaseAgent]:
        return self._agents

    async def handle_chat(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or uuid.uuid4().hex

        input_verdict = await self._guardrails.check(request.message)
        if not input_verdict.allowed:
            await self._events.publish(
                AgentEvent(
                    type="guardrail.blocked",
                    source_agent="orchestrator",
                    session_id=session_id,
                    payload={"stage": "input", "category": input_verdict.category, "reason": input_verdict.reason},
                )
            )
            return ChatResponse(
                session_id=session_id,
                agent="guardrails",
                reply="I can't help with that request.",
                guardrail=input_verdict,
            )

        agent_id = request.agent if request.agent in self._agents else route(request.message, self._agents)
        agent = self._agents[agent_id]
        await self._goals.set_goal(session_id, goal=request.message, agent_id=agent_id)

        history = await self._short_term.get_history(session_id)
        user_message = Message(role="user", content=request.message)
        history_plus_new = [*history, user_message]

        result = await agent.run(history_plus_new, user_id=request.user_id, session_id=session_id)

        output_verdict = await self._guardrails.check(result.content)
        reply = result.content if output_verdict.allowed else "I can't share that response — it was flagged by content safety."

        await self._short_term.append(session_id, user_message)
        await self._short_term.append(session_id, Message(role="assistant", content=reply, name=agent_id))

        event_type = "approval.requested" if result.requires_approval else "chat.completed"
        await self._events.publish(
            AgentEvent(
                type=event_type,
                source_agent=agent_id,
                session_id=session_id,
                payload={"tool_calls": [tc.name for tc in result.tool_calls]},
            )
        )

        return ChatResponse(
            session_id=session_id,
            agent=agent_id,
            reply=reply,
            tool_calls=result.tool_calls,
            guardrail=output_verdict,
            requires_approval=result.requires_approval,
            approval_id=result.approval.id if result.approval else None,
        )
