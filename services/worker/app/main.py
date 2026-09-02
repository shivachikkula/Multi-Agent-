"""Event & Async Processing worker.

Drains the async event bus (Redis Streams locally / Azure Service Bus in
production — the diagram's dashed 'Async Flow' arrows) and persists an
audit trail entry per event, implementing the 'Audit & Logging' node under
Agent Runtime Services independently of the orchestrator's synchronous
request/response path.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from core.config import get_settings
from core.data.document_store import get_document_store
from core.events.factory import get_event_bus
from core.observability.logging_config import configure_logging
from core.observability.tracing import configure_tracing
from core.schemas import AgentEvent

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("worker")

EVENTS_PROCESSED = Counter("worker_events_processed_total", "Events processed by the worker", ["type"])


async def _process(event: AgentEvent, document_store) -> None:
    await document_store.upsert(
        "audit_log",
        event.id,
        {
            "type": event.type,
            "source_agent": event.source_agent,
            "session_id": event.session_id,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
        },
    )
    EVENTS_PROCESSED.labels(type=event.type).inc()
    logger.info(
        "event processed",
        extra={
            "extra_fields": {
                "event_id": event.id,
                "type": event.type,
                "source_agent": event.source_agent,
                "session_id": event.session_id,
            }
        },
    )


async def _consume_loop(app: FastAPI) -> None:
    async for event in app.state.events.consume():
        try:
            await _process(event, app.state.document_store)
        except Exception:
            logger.exception("failed to process event %s", event.id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing(settings)
    app.state.events = get_event_bus(settings)
    app.state.document_store = get_document_store(settings)
    app.state.consumer_task = asyncio.create_task(_consume_loop(app))
    logger.info("worker ready")
    yield
    app.state.consumer_task.cancel()


app = FastAPI(title="Multi-Agent Platform — Worker", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "worker"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/audit")
async def recent_audit_events(session_id: str | None = None):
    filters = {"session_id": session_id} if session_id else {}
    return await app.state.document_store.query("audit_log", **filters)
