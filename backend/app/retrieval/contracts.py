"""Typed contracts for the retrieval subsystem.

No retrieval service may import an SDK-specific result type. All data flows
through the dataclasses and protocols defined here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class RetrievalUnavailable(Exception):
    """Raised when a retrieval provider (embedding, rerank, or vector store)
    is unreachable or returns an unexpected response.

    Callers must never receive raw provider exceptions or credentials.
    The message is always the user-facing Chinese string; diagnostic detail
    is logged separately.
    """

    def __init__(self, message: str = "检索服务暂不可用") -> None:
        super().__init__(message)


@dataclass(frozen=True)
class HybridEmbedding:
    """A dense + sparse hybrid embedding vector."""

    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]


@dataclass(frozen=True)
class RerankResult:
    """A single reranked document with its original index and relevance score."""

    index: int
    score: float


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding providers that produce hybrid vectors."""

    async def embed_documents(self, texts: list[str]) -> list[HybridEmbedding]: ...
    async def embed_query(self, text: str) -> HybridEmbedding: ...


@runtime_checkable
class Reranker(Protocol):
    """Protocol for reranking providers."""

    async def rerank(self, query: str, documents: list[str]) -> list[RerankResult]: ...


@dataclass(frozen=True)
class IndexedSource:
    """A previously indexed source record returned by list_indexed_sources."""

    point_id: str
    source_id: str
    content_hash: str


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector store backends with hybrid search."""

    async def ensure_collection(self) -> None: ...
    async def upsert(self, points: list[dict]) -> None: ...
    async def hybrid_search(
        self,
        query: HybridEmbedding,
        tenant_key: str,
        limit: int = 10,
        dense_limit: int = 20,
        sparse_limit: int = 20,
    ) -> list[dict]: ...
    async def list_indexed_sources(self, tenant_key: str) -> list[IndexedSource]: ...
    async def delete_point_ids(self, ids: list[str]) -> None: ...
    async def delete_tenant(self, tenant_key: str) -> None: ...
