"""'Cosmos DB (RAG / NoSQL)' box — Azure Cosmos DB when configured, an
in-memory dict store otherwise. Used for loosely-structured agent artifacts
(e.g. saved plans, per-agent scratch documents) that don't need the
relational schema in ``sql_store``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.config import Settings


class DocumentStore(ABC):
    @abstractmethod
    async def upsert(self, container: str, doc_id: str, document: dict[str, Any]) -> None: ...

    @abstractmethod
    async def get(self, container: str, doc_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def query(self, container: str, **filters: Any) -> list[dict[str, Any]]: ...


class InMemoryDocumentStore(DocumentStore):
    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, Any]]] = {}

    async def upsert(self, container: str, doc_id: str, document: dict[str, Any]) -> None:
        self._data.setdefault(container, {})[doc_id] = {"id": doc_id, **document}

    async def get(self, container: str, doc_id: str) -> dict[str, Any] | None:
        return self._data.get(container, {}).get(doc_id)

    async def query(self, container: str, **filters: Any) -> list[dict[str, Any]]:
        docs = list(self._data.get(container, {}).values())
        if not filters:
            return docs
        return [d for d in docs if all(d.get(k) == v for k, v in filters.items())]


class CosmosDocumentStore(DocumentStore):
    def __init__(self, settings: Settings) -> None:
        from azure.cosmos.aio import CosmosClient

        self._client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
        self._database_name = "agentdb"

    async def _container(self, name: str):
        db = self._client.get_database_client(self._database_name)
        return db.get_container_client(name)

    async def upsert(self, container: str, doc_id: str, document: dict[str, Any]) -> None:
        c = await self._container(container)
        await c.upsert_item({"id": doc_id, **document})

    async def get(self, container: str, doc_id: str) -> dict[str, Any] | None:
        c = await self._container(container)
        try:
            return await c.read_item(item=doc_id, partition_key=doc_id)
        except Exception:
            return None

    async def query(self, container: str, **filters: Any) -> list[dict[str, Any]]:
        c = await self._container(container)
        items = []
        async for item in c.read_all_items():
            if all(item.get(k) == v for k, v in filters.items()):
                items.append(item)
        return items


def get_document_store(settings: Settings) -> DocumentStore:
    if settings.has_cosmos:
        return CosmosDocumentStore(settings)
    return InMemoryDocumentStore()
