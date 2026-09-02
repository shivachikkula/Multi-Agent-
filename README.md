# Multi-Agent Platform

A working multi-agent application that implements the **Agentic AI Architecture
on Azure** reference diagram end-to-end: an AI Gateway, an Agent Orchestration
Layer (planning, tool selection, memory, guardrails, goal management,
agent-to-agent communication), example agents, tools/connectors, enterprise
data & knowledge, LLM services, event-driven async processing, human-in-the-loop
approvals, observability, and security — all runnable today with **zero Azure
resources**, and ready to point at real Azure services the moment you add
credentials.

## Quick start

```bash
cp .env.example .env         # defaults run entirely on local/mock backends
docker compose up --build
```

- Gateway: http://localhost:8000 (send requests here)
- Orchestrator (internal): http://localhost:8001
- Worker (internal, async event consumer): http://localhost:8002
- Reviewer UI (human-in-the-loop): open `reviewer_ui/index.html` in a browser

```bash
curl -H "X-API-Key: dev-local-key" -H "Content-Type: application/json" \
  -d '{"user_id":"alice","message":"The VPN is down, can you check system status?"}' \
  http://localhost:8000/v1/chat
```

With no Azure credentials configured, agents run against an offline **mock
LLM** so the whole request path (auth → rate limit → routing → guardrails →
tool calls → memory → HITL → async audit log) is fully exercised without any
cloud account. Set the Azure OpenAI variables in `.env` and every agent
automatically starts using GPT-4o instead — no code changes.

### Try the human-in-the-loop flow

```bash
# Over the threshold ($1,000 by default) -> routed to a human approver
curl -H "X-API-Key: dev-local-key" -H "Content-Type: application/json" \
  -d '{"user_id":"bob","message":"Submit a travel expense report for $5000"}' \
  http://localhost:8000/v1/chat
# -> {"requires_approval": true, "approval_id": "..."}

curl -H "X-API-Key: dev-local-key" http://localhost:8000/v1/approvals
curl -H "X-API-Key: dev-local-key" -H "Content-Type: application/json" \
  -d '{"approved": true, "decided_by": "reviewer1"}' \
  http://localhost:8000/v1/approvals/<approval_id>/decide
```

Or use `reviewer_ui/index.html` — a static approve/reject console for the
same API.

## Architecture mapping

Every box in the reference diagram maps to a specific module. Local
fallbacks mean the whole stack runs with no Azure account; each adapter
switches to the real Azure service automatically the moment its
environment variables are set (see `.env.example`).

| Diagram box | Code | Local fallback | Azure backend |
|---|---|---|---|
| **AI Gateway** (APIM) | `services/gateway` | — (gateway has no Azure equivalent needed locally) | Deploy behind Azure API Management, or as-is on Container Apps |
| ↳ Authentication & Authorization | `services/gateway/app/auth.py` | Static API keys | Entra ID JWT validation (`core/security/identity.py`) |
| ↳ Rate Limiting & Quotas | `services/gateway/app/rate_limit.py` | Redis fixed-window counter | Azure Cache for Redis (same code) |
| ↳ Model Routing & Failover | `services/gateway/app/routing.py` | HTTP failover to a secondary orchestrator URL | Multiple Container Apps revisions/regions |
| ↳ Prompt/Response Policies | `services/gateway/app/main.py` (`MAX_MESSAGE_CHARS`) | Length guard | APIM policies |
| ↳ Logging, Cost & Analytics | `services/gateway/app/main.py` middleware | JSON logs + Prometheus counters | Azure Monitor |
| ↳ Versioning & Governance | `/v1/*` route prefix | — | APIM API versions |
| **Agent Orchestration Layer** | `services/orchestrator`, `core/orchestrator` | Runs as a FastAPI app in any container | Azure Container Apps / AKS / Azure Functions |
| ↳ Planning & Reasoning, Tool Selection | `core/agents/base.py` (`BaseAgent.run`) | — | — |
| ↳ Memory & Context | `core/memory/` | — | — |
| ↳ Goal Management | `core/orchestrator/goal_management.py` | — | — |
| ↳ Agent-to-Agent Communication | `core/orchestrator/a2a.py` (`POST /a2a/ask`) | — | — |
| ↳ Guardrails & Safety | `core/orchestrator/guardrails.py` | Regex/keyword heuristic checker | Azure AI Content Safety (`core/llm/content_safety.py`) |
| **Agents (Examples)** | `core/agents/` | — | — |
| ↳ IT Support Agent (full) | `core/agents/it_support_agent.py` + `core/tools/it_tools.py` | — | — |
| ↳ Finance Agent (full, HITL-gated) | `core/agents/finance_agent.py` + `core/tools/finance_tools.py` | — | — |
| ↳ Sales / HR Agents (stubs) | `core/agents/sales_agent.py`, `hr_agent.py` | — | — |
| ↳ Custom Agents | `core/agents/template.py` | copy & extend | — |
| **Agent Runtime Services** | | | |
| ↳ Session Management | `core/schemas.ChatRequest.session_id`, `core/orchestrator/orchestrator.py` | — | — |
| ↳ Short Term Memory | `core/memory/short_term.py` | Redis list | Azure Cache for Redis |
| ↳ Long Term Memory | `core/memory/long_term.py` | Postgres via SQLAlchemy | Azure SQL / Postgres Flexible Server |
| ↳ State Management | `core/memory/state.py` | Redis | Azure Cache for Redis |
| ↳ Audit & Logging | `services/worker` (consumes events, writes `audit_log`) | In-memory/document store | Cosmos DB |
| **Tools & Connectors** | `core/tools/` | | |
| ↳ Web APIs | `core/tools/http_tool.py` | Allow-listed `httpx` calls | — |
| ↳ Azure Functions | `core/tools/calculator_tool.py` (compute stand-in) | Local safe-eval | Real Azure Function via `http_tool` |
| ↳ MCP Servers | `core/tools/mcp_tool.py` | disabled unless `MCP_SERVER_URL` set | any MCP server |
| ↳ Custom Connectors | `core/tools/it_tools.py`, `finance_tools.py`, `sales_agent.py`, `hr_agent.py` | Postgres-backed mocks | Swap for real ITSM/ERP/CRM calls |
| **Enterprise Data & Knowledge** | `core/data/` | | |
| ↳ Azure AI Search (Vector Search) | `core/data/vector_search.py` | In-process cosine similarity over mock/real embeddings | Azure AI Search |
| ↳ Cosmos DB (RAG/NoSQL) | `core/data/document_store.py` | In-memory dict | Azure Cosmos DB |
| ↳ SQL Database (Transactional) | `core/data/sql_store.py` | Postgres | Azure SQL / Postgres Flexible Server |
| ↳ Blob Storage (Documents) | `core/data/blob_store.py` | Local filesystem (`.data/blobs`) | Azure Blob Storage |
| **LLM & AI Services** | `core/llm/` | | |
| ↳ Azure OpenAI (GPT-4o/o1) | `core/llm/azure_openai_provider.py` | `core/llm/mock_provider.py` (offline, deterministic) | Azure OpenAI Service |
| ↳ Azure Content Safety & Guardrails | `core/llm/content_safety.py` | `LocalHeuristicChecker` | `AzureContentSafetyChecker` |
| **Event & Async Processing** | `core/events/`, `services/worker` | | |
| ↳ Azure Event Hub | `core/events/event_hub_adapter.py` | — | activates via `AZURE_EVENT_HUB_CONNECTION_STRING` |
| ↳ Azure Service Bus / Queues | `core/events/service_bus_adapter.py` | Redis Streams (`core/events/local_queue.py`) | activates via `AZURE_SERVICE_BUS_CONNECTION_STRING` |
| **Human in the Loop** | `core/human_in_the_loop/approvals.py`, `reviewer_ui/` | Postgres-backed approval queue + static reviewer UI | same, or plug into Teams/email notifications |
| **Observability & Monitoring** | `core/observability/` | | |
| ↳ Azure Monitor / App Insights | `core/observability/tracing.py` | Console OpenTelemetry exporter | Azure Monitor exporter |
| ↳ Log Analytics Workspace | `core/observability/logging_config.py` | JSON stdout logs | Container Apps' built-in Log Analytics |
| ↳ Alerts & Notifications | `core/observability/metrics.py` (`/metrics`) | Prometheus endpoint | Azure Monitor managed Prometheus scraping |
| **Identity, Security & Governance** | `core/security/` | | |
| ↳ Azure Entra ID | `core/security/identity.py` (`validate_entra_token`) | API-key auth | set `AZURE_TENANT_ID` / `AZURE_AD_AUDIENCE` |
| ↳ Managed Identity | `core/security/identity.py` (`get_managed_identity_credential`), used by `azure_openai_provider.py` | — | set `AZURE_USE_MANAGED_IDENTITY=true` |
| ↳ Azure Key Vault | `core/security/keyvault.py` | env vars (`core/config.py`) | `resolve_secret()` via Managed Identity |
| ↳ Private Endpoints & Networking | N/A in this codebase | `core/tools/http_tool.py` egress allow-list approximates it | VNet + Private Link in the actual deployment |

## Repository layout

```
core/                    Shared domain library (imported by orchestrator + worker)
  config.py              All environment variables, one place
  schemas.py             Pydantic models shared across services
  llm/                   Azure OpenAI + mock provider + content safety
  memory/                Short-term (Redis), long-term (SQL), state (Redis)
  data/                  Vector search, document store, SQL store, blob store
  tools/                 Tool interface + registry + concrete tools
  agents/                BaseAgent + IT Support, Finance, Sales, HR, template
  orchestrator/          Agent registry/routing, guardrails, A2A, goals, orchestrator
  events/                Event bus interface + Redis/Event Hub/Service Bus adapters
  human_in_the_loop/     Approval queue
  security/              Entra ID validation, Key Vault, managed identity
  observability/         Logging, tracing, metrics

services/
  gateway/               AI Gateway (auth, rate limit, routing, policies)
  orchestrator/           Orchestrator service (FastAPI) — /chat /agents /approvals /a2a
  worker/                 Async event consumer — audit log, HITL side-effects

reviewer_ui/index.html   Static human-in-the-loop approve/reject console
tests/                    pytest suite (agents, tools, guardrails, routing, orchestrator, gateway)
docker-compose.yml        redis + postgres + gateway + orchestrator + worker
```

## Adding a new agent

1. Copy `core/agents/template.py`, rename the class, fill in `id`,
   `display_name`, `description`, `system_prompt`, `tool_names`.
2. If it needs new tools, add them under `core/tools/` and register them in
   `build_tool_registry` (`core/orchestrator/agent_registry.py`).
3. Add an instance of your agent to `build_agents` in the same file, and
   optionally add routing keywords to `_ROUTING_KEYWORDS`.
4. If any of its actions are sensitive, override `before_tool_call` like
   `FinanceAgent` does to route through `core/human_in_the_loop/approvals.py`.

That's the entire integration surface — memory, guardrails, gateway routing,
observability, and the reviewer UI all pick it up automatically.

## Running tests

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn httpx redis pydantic pydantic-settings \
  "sqlalchemy[asyncio]" asyncpg aiosqlite prometheus-client \
  opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi \
  "PyJWT[crypto]" pytest pytest-asyncio fakeredis
PYTHONPATH=. pytest tests/ -v
```

Tests run against SQLite (in-memory) and `fakeredis` — no Docker or live
services required. (`services/*/requirements.txt` are the production
container dependency lists.)

## Going to production on Azure

Nothing here provisions Azure resources (no Bicep/Terraform is included).
To point this app at real infrastructure:

1. Deploy `services/gateway`, `services/orchestrator`, `services/worker` as
   three Azure Container Apps (or AKS deployments / Azure Functions).
2. Create the Azure resources named in the mapping table above as needed
   (Azure OpenAI is the only one required to leave mock mode).
3. Set each service's environment variables from `.env.example` — ideally
   via Container Apps' native Key Vault secret references, or resolve them
   in-process at boot with `core/security/keyvault.py`.
4. Set `AZURE_USE_MANAGED_IDENTITY=true` and grant each Container App's
   Managed Identity access to Azure OpenAI / Key Vault / Cosmos / Search /
   Storage / Service Bus as needed, instead of shipping API keys.
5. Put Azure API Management in front of the gateway (or replace the
   gateway service with APIM policies directly) for enterprise-grade
   authentication, quotas, and versioning.
6. Wire `APPLICATIONINSIGHTS_CONNECTION_STRING` for tracing/logs and scrape
   each service's `/metrics` with Azure Monitor managed Prometheus.
