"""AI Gateway service (Azure API Management stand-in).

Owns everything in the diagram's 'AI Gateway' box: authentication &
authorization, rate limiting & quotas, model routing & failover,
prompt/response policies, logging/cost/analytics, and API versioning. It
holds no business logic of its own — every request it accepts is forwarded
to the orchestrator service.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from core.config import get_settings
from core.observability.logging_config import configure_logging
from services.gateway.app.auth import authenticate
from services.gateway.app.rate_limit import RateLimiter
from services.gateway.app.routing import OrchestratorRouter

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("gateway")

GATEWAY_REQUESTS = Counter("gateway_requests_total", "Requests handled by the gateway", ["path", "status"])
GATEWAY_LATENCY = Histogram("gateway_request_latency_seconds", "Gateway request latency", ["path"])

MAX_MESSAGE_CHARS = 8000  # 'Prompt/Response Policies': reject oversized prompts before they hit the LLM


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rate_limiter = RateLimiter(settings.redis_url, settings.gateway_rate_limit_per_minute)
    app.state.router = OrchestratorRouter(settings)
    yield
    await app.state.rate_limiter.close()
    await app.state.router.close()


app = FastAPI(title="Multi-Agent Platform — AI Gateway", version="1.0.0", lifespan=lifespan)

# Demo-only: lets the static reviewer_ui/index.html (opened from disk or any
# origin) call the gateway. Lock this down to specific origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)
except ImportError:
    pass


@app.middleware("http")
async def logging_and_metrics(request: Request, call_next):
    start = time.monotonic()
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
    response = await call_next(request)
    elapsed = time.monotonic() - start
    response.headers["x-request-id"] = request_id
    GATEWAY_REQUESTS.labels(path=request.url.path, status=response.status_code).inc()
    GATEWAY_LATENCY.labels(path=request.url.path).observe(elapsed)
    logger.info(
        "request",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": round(elapsed * 1000, 2),
            }
        },
    )
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def _guarded_forward(request: Request, method: str, path: str, json_body: dict | None = None):
    principal = await authenticate(
        settings,
        x_api_key=request.headers.get("x-api-key"),
        authorization=request.headers.get("authorization"),
    )
    await request.app.state.rate_limiter.enforce(principal.subject)
    response = await request.app.state.router.forward(method, path, json=json_body)
    return JSONResponse(status_code=response.status_code, content=response.json())


@app.post("/v1/chat")
async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "")
    if len(message) > MAX_MESSAGE_CHARS:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"message exceeds {MAX_MESSAGE_CHARS} characters",
        )
    return await _guarded_forward(request, "POST", "/chat", json_body=body)


@app.get("/v1/agents")
async def list_agents(request: Request):
    return await _guarded_forward(request, "GET", "/agents")


@app.get("/v1/approvals")
async def list_approvals(request: Request):
    return await _guarded_forward(request, "GET", "/approvals")


@app.post("/v1/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, request: Request):
    body = await request.json()
    return await _guarded_forward(request, "POST", f"/approvals/{approval_id}/decide", json_body=body)
