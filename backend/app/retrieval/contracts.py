"""Typed contracts for the retrieval subsystem.

No retrieval service may import an SDK-specific result type. All data flows
through the dataclasses and protocols defined here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class RetrievalUnavailable(Exception):
    """Raised when a retrieval provider (embedding, rerank, or vector store)
    is unreachable or returns an unexpected response.

    Callers must never receive raw provider exceptions or credentials.
    The message is always the user-facing Chinese string; diagnostic detail
    is logged separately.
    """

    def __init__(self, message: str = "检索服务暂不可用") -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Embedding & rerank data types
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Search result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetrievedSource:
    """A single source returned by hybrid search.

    Carries the payload fields needed for source projection and diversity
    filtering.  The ``visibility`` field separates writer-visible (``"default"``)
    from guard-only (``"guard"``) sources.
    """

    source_id: str
    source_type: str
    title: str
    preview: str
    locator: dict[str, Any]
    text: str = ""
    visibility: str = "default"
    chapter_id: int | None = None
    importance: str = "minor"


# ---------------------------------------------------------------------------
# Request / response types for the retrieval service
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetrievalRequest:
    """Input to :meth:`RetrievalService.retrieve`.

    Attributes
    ----------
    user_id:
        Owner of the novel (used to build tenant key).
    novel_id:
        Novel to search within.
    query:
        Natural-language query string.
    target_chapter_id:
        The chapter currently being written (for proximity boosting).
    """

    user_id: int
    novel_id: int
    query: str
    target_chapter_id: int | None = None


@dataclass
class RetrievalContext:
    """Output of :meth:`RetrievalService.retrieve`.

    Attributes
    ----------
    writer_items:
        Projected source dicts for the writer context (max 10).
        Each dict has keys: source_id, source_type, title, locator,
        preview, inclusion_reason.  No score fields.
    guard_constraints:
        Guard-only constraint dicts (max 6) derived from guard-visibility
        sources.  Contains name/status/risk wording but NOT hidden_truth
        in the writer_items.
    source_items:
        Combined projected source dicts (writer + guard) without scores.
    diagnostics:
        Raw candidate scores, source IDs, collection version, and
        failure reason.  Only for debugging — never shown to the writer.
    """

    writer_items: list[dict[str, Any]] = field(default_factory=list)
    guard_constraints: list[dict[str, Any]] = field(default_factory=list)
    source_items: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Provider protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class RetrievalProvider(Protocol):
    """Minimal protocol that RetrievalService satisfies.

    Accepts a RetrievalRequest and returns a RetrievalContext.
    """

    async def retrieve(self, request: Any) -> Any: ...


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
        visibility: str = "default",
        limit: int = 10,
        dense_limit: int = 24,
        sparse_limit: int = 24,
    ) -> list[RetrievedSource]: ...
    async def list_indexed_sources(self, tenant_key: str) -> list[IndexedSource]: ...
    async def delete_point_ids(self, ids: list[str]) -> None: ...
    async def delete_tenant(self, tenant_key: str) -> None: ...
