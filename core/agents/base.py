"""Base agent: the reasoning loop shared by every specialized agent.

Implements 'Planning & Reasoning' + 'Tool Selection' from the Agent
Orchestrator box: repeatedly call the LLM, execute any tool it selects, feed
the result back, until it produces a final answer or a subclass pauses the
loop for human approval (see ``before_tool_call``).
"""
from __future__ import annotations

import json
from abc import ABC
from dataclasses import dataclass, field
from typing import Any

from core.llm.base import LLMProvider
from core.schemas import ApprovalRequest, Message, ToolCall
from core.tools.registry import ToolRegistry


@dataclass
class AgentRunResult:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    requires_approval: bool = False
    approval: ApprovalRequest | None = None


class BaseAgent(ABC):
    id: str = "base"
    display_name: str = "Base Agent"
    description: str = "Generic agent."
    system_prompt: str = "You are a helpful enterprise assistant."
    #: Tool names (from the shared ToolRegistry) this agent is allowed to call.
    tool_names: list[str] = []
    max_tool_iterations: int = 4

    def __init__(self, llm: LLMProvider, tools: ToolRegistry) -> None:
        self._llm = llm
        self._tools = tools

    async def run(self, messages: list[Message], *, user_id: str, session_id: str) -> AgentRunResult:
        convo: list[Message] = [Message(role="system", content=self.system_prompt), *messages]
        tool_calls_made: list[ToolCall] = []

        for _ in range(self.max_tool_iterations):
            specs = self._tools.specs(self.tool_names) if self.tool_names else None
            response = await self._llm.chat(convo, tools=specs)

            if not response.tool_calls:
                return AgentRunResult(content=response.content or "", tool_calls=tool_calls_made)

            for tc in response.tool_calls:
                raw_args = tc.get("arguments", "{}")
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

                approval = await self.before_tool_call(
                    tc["name"], args, user_id=user_id, session_id=session_id
                )
                if approval is not None:
                    return AgentRunResult(
                        content=(
                            f"This action ('{tc['name']}') needs approval before I can proceed: "
                            f"{approval.reason}"
                        ),
                        tool_calls=tool_calls_made,
                        requires_approval=True,
                        approval=approval,
                    )

                tool = self._tools.get(tc["name"])
                record = ToolCall(id=tc.get("id", tc["name"]), name=tc["name"], arguments=args)
                if tool is None:
                    record.error = "unknown tool"
                    result: Any = f"Error: unknown tool '{tc['name']}'"
                else:
                    try:
                        result = await tool.run(user_id=user_id, session_id=session_id, **args)
                        record.result = result
                    except Exception as exc:  # tool failures shouldn't crash the agent turn
                        record.error = str(exc)
                        result = f"Error running {tc['name']}: {exc}"

                tool_calls_made.append(record)
                convo.append(Message(role="tool", name=tc["name"], tool_call_id=record.id, content=str(result)))

        return AgentRunResult(
            content="I reached my reasoning-step limit before finishing — please rephrase or simplify the request.",
            tool_calls=tool_calls_made,
        )

    async def before_tool_call(
        self, name: str, args: dict[str, Any], *, user_id: str, session_id: str
    ) -> ApprovalRequest | None:
        """Return an ``ApprovalRequest`` to pause execution for human review,
        or ``None`` to let the tool call proceed. Overridden by agents with
        sensitive actions (see ``FinanceAgent``)."""
        return None
