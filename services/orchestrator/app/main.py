"""Agent Orchestration Layer service.

Hosts the Agent Orchestrator (planning, tool selection, memory, guardrails,
goal management, agent-to-agent communication), the example agents, and
the Human-in-the-loop approvals API. Deployed behind the gateway service —
see the diagram's 'Agent Orchestration Layer (Azure Container Apps / AKS /
Azure Functions)' box.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from core.config import get_settings
from core.data.document_store import get_document_store
from core.data.sql_store import SqlStore
from core.data.vector_search import DEMO_KNOWLEDGE_BASE, get_vector_index
from core.events.factory import get_event_bus
from core.human_in_the_loop.approvals import ApprovalService
from core.llm.content_safety import get_content_safety_checker
from core.llm.factory import get_llm_provider
from core.memory.long_term import LongTermMemory
from core.memory.short_term import ShortTermMemory
from core.memory.state import StateStore
from core.observability.logging_config import configure_logging
from core.observability.tracing import configure_tracing
from core.orchestrator.agent_registry import build_agents, build_tool_registry
from core.orchestrator.goal_management import GoalManager
from core.orchestrator.guardrails import GuardrailsEngine
from core.orchestrator.orchestrator import Orchestrator
from core.schemas import AgentEvent, ChatRequest, ChatResponse

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("orchestrator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing(settings)

    sql = SqlStore(settings.sql_database_url)
    await sql.init_models()
    await sql.seed_demo_data()

    llm = get_llm_provider(settings)
    vector_index = get_vector_index(settings, llm)
    await vector_index.upsert(DEMO_KNOWLEDGE_BASE)

    document_store = get_document_store(settings)
    content_safety = get_content_safety_checker(settings)
    guardrails = GuardrailsEngine(content_safety)

    tools = await build_tool_registry(sql, vector_index, settings)
    approvals = ApprovalService(sql)
    agents, a2a = build_agents(llm, tools, approvals, settings)

    short_term = ShortTermMemory(settings.redis_url)
    long_term = LongTermMemory(sql.session_factory)
    state = StateStore(settings.redis_url)
    goals = GoalManager(state)
    events = get_event_bus(settings)

    orchestrator = Orchestrator(agents, short_term, long_term, goals, guardrails, events)

    app.state.settings = settings
    app.state.sql = sql
    app.state.tools = tools
    app.state.approvals = approvals
    app.state.orchestrator = orchestrator
    app.state.agents = agents
    app.state.a2a = a2a
    app.state.events = events
    app.state.document_store = document_store

    logger.info(
        "orchestrator ready",
        extra={
            "extra_fields": {
                "llm_provider": llm.name,
                "agents": list(agents.keys()),
                "azure_openai": settings.has_azure_openai,
                "azure_search": settings.has_azure_search,
                "cosmos": settings.has_cosmos,
            }
        },
    )
    yield

    await sql.dispose()
    await short_term.close()
    await state.close()


app = FastAPI(title="Multi-Agent Platform — Orchestrator", version="1.0.0", lifespan=lifespan)

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)
except ImportError:
    pass


@app.get("/health")
async def health():
    return {"status": "ok", "service": "orchestrator"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return await app.state.orchestrator.handle_chat(request)


@app.get("/agents")
async def list_agents():
    return [
        {"id": a.id, "display_name": a.display_name, "description": a.description, "tools": a.tool_names}
        for a in app.state.agents.values()
    ]


class A2ARequest(BaseModel):
    to_agent: str
    question: str
    user_id: str = "system"
    session_id: str = "a2a"


@app.post("/a2a/ask")
async def a2a_ask(request: A2ARequest):
    """Demonstrates the 'Agent-to-Agent Communication' node: one agent (or
    an external caller, for testing) asks another agent a question
    directly, bypassing routing/guardrails since it's an internal call."""
    answer = await app.state.a2a.ask(
        to_agent=request.to_agent,
        question=request.question,
        user_id=request.user_id,
        session_id=request.session_id,
    )
    return {"from": "orchestrator", "to_agent": request.to_agent, "answer": answer}


@app.get("/approvals")
async def list_approvals():
    return await app.state.approvals.list_pending()


class ApprovalDecision(BaseModel):
    approved: bool
    decided_by: str = "reviewer"


@app.post("/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, decision: ApprovalDecision):
    approval = await app.state.approvals.decide(approval_id, decision.approved, decision.decided_by)
    if approval is None:
        raise HTTPException(404, "approval not found")

    if decision.approved:
        tool = app.state.tools.get(approval.action)
        if tool is not None:
            try:
                await tool.run(**approval.payload)
            except Exception as exc:  # surfaced to the reviewer, approval stays recorded as approved
                logger.error("approved action failed to execute", extra={"extra_fields": {"error": str(exc)}})

    await app.state.events.publish(
        AgentEvent(
            type="approval.decided",
            source_agent=approval.agent,
            session_id=approval.session_id,
            payload={"approval_id": approval_id, "approved": decision.approved},
        )
    )
    return approval
