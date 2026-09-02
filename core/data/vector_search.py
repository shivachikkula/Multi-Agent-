"""'Azure AI Search (Vector Search)' box, with an in-process cosine-similarity
fallback so knowledge-base search works with zero cloud resources.

Backs the knowledge_search tool used by every agent for RAG.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from core.config import Settings
from core.llm.base import LLMProvider


@dataclass
class SearchDocument:
    id: str
    title: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    document: SearchDocument
    score: float


class VectorSearchIndex(ABC):
    @abstractmethod
    async def upsert(self, documents: list[SearchDocument]) -> None: ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 3) -> list[SearchResult]: ...


class LocalVectorIndex(VectorSearchIndex):
    """Cosine-similarity search over in-memory embeddings via the active
    LLM provider's ``embed`` method (mock or Azure OpenAI embeddings)."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm
        self._docs: list[SearchDocument] = []
        self._vectors: list[list[float]] = []

    async def upsert(self, documents: list[SearchDocument]) -> None:
        vectors = await self._llm.embed([f"{d.title}\n{d.content}" for d in documents])
        self._docs.extend(documents)
        self._vectors.extend(vectors)

    async def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        if not self._docs:
            return []
        [query_vec] = await self._llm.embed([query])
        scored = [
            (self._cosine(query_vec, vec), doc) for vec, doc in zip(self._vectors, self._docs)
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [SearchResult(document=doc, score=score) for score, doc in scored[:top_k]]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5 or 1e-9
        nb = sum(y * y for y in b) ** 0.5 or 1e-9
        return dot / (na * nb)


class AzureAISearchIndex(VectorSearchIndex):
    def __init__(self, settings: Settings) -> None:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents.aio import SearchClient

        self._client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index,
            credential=AzureKeyCredential(settings.azure_search_api_key),
        )

    async def upsert(self, documents: list[SearchDocument]) -> None:
        await self._client.upload_documents(
            documents=[{"id": d.id, "title": d.title, "content": d.content, **d.metadata} for d in documents]
        )

    async def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        results = await self._client.search(search_text=query, top=top_k)
        out: list[SearchResult] = []
        async for r in results:
            out.append(
                SearchResult(
                    document=SearchDocument(id=r["id"], title=r.get("title", ""), content=r.get("content", "")),
                    score=r.get("@search.score", 0.0),
                )
            )
        return out


def get_vector_index(settings: Settings, llm: LLMProvider) -> VectorSearchIndex:
    if settings.has_azure_search:
        return AzureAISearchIndex(settings)
    return LocalVectorIndex(llm)


DEMO_KNOWLEDGE_BASE = [
    SearchDocument(
        id="kb-1",
        title="VPN connection troubleshooting",
        content=(
            "If a user cannot connect to the corporate VPN: 1) confirm the client is updated to "
            "the latest version, 2) verify multi-factor auth is enrolled, 3) check for regional "
            "outages on the status page, 4) as a last resort, escalate to network engineering."
        ),
    ),
    SearchDocument(
        id="kb-2",
        title="Password reset policy",
        content=(
            "Self-service password reset is available via the identity portal. Resets requiring "
            "identity verification (e.g. after a suspected compromise) must be escalated to a "
            "human security analyst via approval workflow before being performed."
        ),
    ),
    SearchDocument(
        id="kb-3",
        title="Expense approval policy",
        content=(
            "Expenses under $1,000 are auto-approved if within the submitter's department budget. "
            "Expenses at or above $1,000 require human finance-manager approval regardless of "
            "remaining budget."
        ),
    ),
    SearchDocument(
        id="kb-4",
        title="Travel & expense categories",
        content=(
            "Reimbursable categories: airfare, lodging, ground transport, meals (per-diem capped), "
            "and client entertainment (requires attendee list). Personal items are never reimbursable."
        ),
    ),
]
