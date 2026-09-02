"""RAG tool shared by every agent: searches the vector index (Azure AI
Search or local fallback) seeded from the 'Enterprise Data & Knowledge' box.
"""
from __future__ import annotations

from typing import Any

from core.data.vector_search import VectorSearchIndex
from core.tools.base import Tool


class KnowledgeSearchTool(Tool):
    name = "search_knowledge_base"
    description = "Search the enterprise knowledge base for policies, runbooks, and FAQs."
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "What to search for."}},
        "required": ["query"],
    }

    def __init__(self, index: VectorSearchIndex) -> None:
        self._index = index

    async def run(self, query: str, **_: Any) -> str:
        results = await self._index.search(query, top_k=3)
        if not results:
            return "No relevant documents found."
        return "\n\n".join(f"[{r.document.title}] (score={r.score:.2f}) {r.document.content}" for r in results)
