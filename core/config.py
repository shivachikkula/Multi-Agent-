"""Central configuration, sourced from environment variables (12-factor).

In Azure, these would be populated via Container Apps environment variables
whose secret values are pulled from Key Vault by a Managed Identity — see
``core.security.keyvault``. Locally, a ``.env`` file (see ``.env.example``)
is enough to run the whole stack with no cloud account at all.
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Identity, Security & Governance -----------------------------------
    entra_tenant_id: str | None = Field(default=None, alias="AZURE_TENANT_ID")
    entra_audience: str | None = Field(default=None, alias="AZURE_AD_AUDIENCE")
    gateway_api_keys: str = Field(default="dev-local-key", alias="GATEWAY_API_KEYS")
    key_vault_uri: str | None = Field(default=None, alias="AZURE_KEY_VAULT_URI")

    # --- AI Gateway ----------------------------------------------------------
    gateway_rate_limit_per_minute: int = Field(default=60, alias="GATEWAY_RATE_LIMIT_PER_MINUTE")
    orchestrator_base_url: str = Field(default="http://orchestrator:8001", alias="ORCHESTRATOR_BASE_URL")
    orchestrator_failover_url: str | None = Field(default=None, alias="ORCHESTRATOR_FAILOVER_URL")

    # --- LLM & AI Services -----------------------------------------------
    azure_openai_endpoint: str | None = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: str | None = Field(default=None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_deployment: str = Field(default="gpt-4o", alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(default="2024-08-01-preview", alias="AZURE_OPENAI_API_VERSION")
    azure_content_safety_endpoint: str | None = Field(default=None, alias="AZURE_CONTENT_SAFETY_ENDPOINT")
    azure_content_safety_api_key: str | None = Field(default=None, alias="AZURE_CONTENT_SAFETY_API_KEY")

    # --- Enterprise Data & Knowledge ---------------------------------------
    azure_search_endpoint: str | None = Field(default=None, alias="AZURE_SEARCH_ENDPOINT")
    azure_search_api_key: str | None = Field(default=None, alias="AZURE_SEARCH_API_KEY")
    azure_search_index: str = Field(default="knowledge-base", alias="AZURE_SEARCH_INDEX")
    cosmos_endpoint: str | None = Field(default=None, alias="AZURE_COSMOS_ENDPOINT")
    cosmos_key: str | None = Field(default=None, alias="AZURE_COSMOS_KEY")
    sql_database_url: str = Field(
        default="postgresql+asyncpg://agent:agent@postgres:5432/agentdb",
        alias="SQL_DATABASE_URL",
    )
    blob_connection_string: str | None = Field(default=None, alias="AZURE_STORAGE_CONNECTION_STRING")
    blob_container: str = Field(default="documents", alias="AZURE_STORAGE_CONTAINER")

    # --- Event & Async Processing -------------------------------------------
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    event_hub_connection_string: str | None = Field(default=None, alias="AZURE_EVENT_HUB_CONNECTION_STRING")
    service_bus_connection_string: str | None = Field(default=None, alias="AZURE_SERVICE_BUS_CONNECTION_STRING")
    service_bus_queue: str = Field(default="agent-tasks", alias="AZURE_SERVICE_BUS_QUEUE")

    # --- Observability & Monitoring -----------------------------------------
    applicationinsights_connection_string: str | None = Field(
        default=None, alias="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )
    otel_service_name: str = Field(default="multi-agent-platform", alias="OTEL_SERVICE_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Tools & Connectors ---------------------------------------------------
    mcp_server_url: str | None = Field(default=None, alias="MCP_SERVER_URL")

    # --- Human in the loop ---------------------------------------------------
    hitl_finance_approval_threshold_usd: float = Field(
        default=1000.0, alias="HITL_FINANCE_APPROVAL_THRESHOLD_USD"
    )

    @property
    def gateway_api_key_set(self) -> set[str]:
        return {k.strip() for k in self.gateway_api_keys.split(",") if k.strip()}

    @property
    def has_azure_openai(self) -> bool:
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key)

    @property
    def has_azure_search(self) -> bool:
        return bool(self.azure_search_endpoint and self.azure_search_api_key)

    @property
    def has_cosmos(self) -> bool:
        return bool(self.cosmos_endpoint and self.cosmos_key)

    @property
    def has_blob(self) -> bool:
        return bool(self.blob_connection_string)

    @property
    def has_event_hub(self) -> bool:
        return bool(self.event_hub_connection_string)

    @property
    def has_service_bus(self) -> bool:
        return bool(self.service_bus_connection_string)

    @property
    def has_content_safety(self) -> bool:
        return bool(self.azure_content_safety_endpoint and self.azure_content_safety_api_key)

    @property
    def has_app_insights(self) -> bool:
        return bool(self.applicationinsights_connection_string)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def env_flag(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}
