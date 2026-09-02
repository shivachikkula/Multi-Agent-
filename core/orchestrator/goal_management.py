"""'Goal Management' node inside the Agent Orchestrator box.

Tracks the active high-level goal and which agent owns it for a session, on
top of the generic ``StateStore`` (which just persists a JSON blob). Kept
deliberately small: a goal here is "what the user is currently trying to
get done", separate from the step-by-step tool-call state the agent loop
itself manages in memory.
"""
from __future__ import annotations

from core.memory.state import StateStore


class GoalManager:
    def __init__(self, state: StateStore) -> None:
        self._state = state

    async def set_goal(self, session_id: str, goal: str, agent_id: str) -> None:
        await self._state.update(session_id, goal=goal, owning_agent=agent_id)

    async def get_goal(self, session_id: str) -> dict:
        state = await self._state.get(session_id)
        return {"goal": state.get("goal"), "owning_agent": state.get("owning_agent")}

    async def clear_goal(self, session_id: str) -> None:
        await self._state.update(session_id, goal=None, owning_agent=None)
