"""Hybrid retrieval service with writer/guard separation and fallback.

Orchestrates embedding, hybrid search, reranking, and diversity filtering
to produce a :class:`RetrievalContext` with separated writer and guard
outputs.  Catches :class:`RetrievalUnavailable` at this facade boundary
and returns empty lists with fallback diagnostics.

Fixed limits (from approved design):
- Dense/sparse recall: 24 each
- Fusion limit: 20
- Final writer items: 10
- Final guard constraints: 6
"""
from __future__ import annotations

import logging
from typing import Any

from app.retrieval.contracts import (
    EmbeddingProvider,
    Reranker,
    RetrievedSource,
    RetrievalContext,
    RetrievalRequest,
    RetrievalUnavailable,
    VectorStore,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixed retrieval limits
# ---------------------------------------------------------------------------

_DENSE_LIMIT = 24
_SPARSE_LIMIT = 24
_FUSION_LIMIT = 20
_WRITER_BUDGET = 10
_GUARD_BUDGET = 6
_MAX_CHAPTER_SCENES = 2  # per chapter
_TOKEN_BUDGET_ESTIMATE = 4000  # rough CJK char estimate
_COLLECTION_VERSION = "novel-context-v1"


# ---------------------------------------------------------------------------
# Source projection
# ---------------------------------------------------------------------------


def to_source_item(item: RetrievedSource, reason: str) -> dict[str, Any]:
    """Project a RetrievedSource into a source_items dict without scores."""
    return {
        "source_id": item.source_id,
        "source_type": item.source_type,
        "title": item.title,
        "locator": item.locator,
        "preview": item.preview,
        "inclusion_reason": reason,
    }


def to_writer_context_item(item: RetrievedSource, reason: str) -> dict[str, Any]:
    """Project a writer item with usable text but no retrieval scores."""
    projected = to_source_item(item, reason)
    projected["text"] = item.text or item.preview
    return projected


# ---------------------------------------------------------------------------
# RetrievalService
# ---------------------------------------------------------------------------


class RetrievalService:
    """Facade that orchestrates the full retrieval pipeline.

    Steps:
    1. Embed the query.
    2. Run hybrid search twice: once with visibility="writer", once
       with visibility="guard".
    3. Rerank the fused writer candidates.
    4. Apply diversity filtering (dedup, per-chapter scene cap,
       importance promotion, budget limits).
    5. Build guard constraints from guard results.
    6. Assemble RetrievalContext with diagnostics.

    Parameters
    ----------
    embedder:
        An :class:`EmbeddingProvider` for computing query embeddings.
    reranker:
        A :class:`Reranker` for relevance reranking.
    store:
        A :class:`VectorStore` for hybrid search.
    """

    def __init__(
        self,
        *,
        embedder: EmbeddingProvider,
        reranker: Reranker,
        store: VectorStore,
    ) -> None:
        self._embedder = embedder
        self._reranker = reranker
        self._store = store

    async def retrieve(self, request: RetrievalRequest) -> RetrievalContext:
        """Execute the full retrieval pipeline for the given request.

        Catches :class:`RetrievalUnavailable` and returns a fallback
        :class:`RetrievalContext` with empty lists.  Does NOT catch
        programmer errors (TypeError, ValueError, etc.).
        """
        try:
            return await self._retrieve_impl(request)
        except RetrievalUnavailable:
            return RetrievalContext(
                writer_items=[],
                guard_constraints=[],
                source_items=[],
                diagnostics={
                    "retrieval_status": "fallback",
                    "reason": "service_unavailable",
                },
            )

    async def _retrieve_impl(self, request: RetrievalRequest) -> RetrievalContext:
        """Internal implementation that may raise RetrievalUnavailable."""
        tenant_key = f"{request.user_id}:{request.novel_id}"

        # Step 1: Embed the query
        query_embedding = await self._embedder.embed_query(request.query)

        # Step 2: Hybrid search — writer and guard separately
        writer_candidates = await self._store.hybrid_search(
            query=query_embedding,
            tenant_key=tenant_key,
            visibility="writer",
            limit=_FUSION_LIMIT,
            dense_limit=_DENSE_LIMIT,
            sparse_limit=_SPARSE_LIMIT,
        )

        guard_candidates = await self._store.hybrid_search(
            query=query_embedding,
            tenant_key=tenant_key,
            visibility="guard",
            limit=_FUSION_LIMIT,
            dense_limit=_DENSE_LIMIT,
            sparse_limit=_SPARSE_LIMIT,
        )

        # Step 3: Rerank writer candidates
        reranked_writer = await self._rerank_candidates(
            request.query,
            writer_candidates,
            target_chapter_id=request.target_chapter_id,
        )

        # Step 4: Diversity filtering on writer items
        writer_items = self._apply_diversity_filter(reranked_writer)

        # Step 5: Build guard constraints
        guard_constraints = self._build_guard_constraints(guard_candidates)

        # Step 6: Build source_items (combined projection)
        source_items = self._build_source_items(writer_items, guard_constraints)

        # Step 7: Assemble diagnostics
        diagnostics = self._build_diagnostics(
            writer_candidates, guard_candidates, reranked_writer
        )

        return RetrievalContext(
            writer_items=writer_items,
            guard_constraints=guard_constraints,
            source_items=source_items,
            diagnostics=diagnostics,
        )

    async def _rerank_candidates(
        self,
        query: str,
        candidates: list[RetrievedSource],
        *,
        target_chapter_id: int | None = None,
    ) -> list[RetrievedSource]:
        """Rerank candidates and return them in reranked order.

        The reranker returns indices into the original documents list;
        we reorder candidates accordingly, preserving the reranker's
        returned input indices order.
        """
        if not candidates:
            return []

        documents = [c.title for c in candidates]
        rerank_results = await self._reranker.rerank(query, documents)

        # Reorder candidates by the reranker's returned indices
        reranked = []
        for rr in rerank_results:
            if 0 <= rr.index < len(candidates):
                reranked.append(candidates[rr.index])

        # Append any candidates not covered by the reranker
        seen_indices = {rr.index for rr in rerank_results}
        for i, candidate in enumerate(candidates):
            if i not in seen_indices:
                reranked.append(candidate)

        if target_chapter_id is not None:
            # Keep reranker order within each group, while preferring sources
            # from the chapter currently being extracted or revised.
            reranked.sort(key=lambda candidate: candidate.chapter_id != target_chapter_id)

        return reranked

    def _apply_diversity_filter(
        self, candidates: list[RetrievedSource]
    ) -> list[dict[str, Any]]:
        """Apply diversity rules to produce writer_items.

        Rules applied in order:
        1. Reject duplicate source_id.
        2. Permit at most 2 chapter_scene items per chapter.
        3. Take high-importance facts/settings before lower-ranked
           duplicate scenes (scenes that would exceed the per-chapter
           cap are skipped; high-importance non-scene items that come
           later in the reranked list are still included).
        4. Stop at the item and estimated-token budgets.
        """
        seen_ids: set[str] = set()
        chapter_scene_counts: dict[int, int] = {}
        items: list[dict[str, Any]] = []
        estimated_tokens = 0

        # Two-pass approach:
        # Pass 1: Process in rerank order, applying dedup and scene cap.
        #         Collect high-importance items that don't fit due to token budget.
        # Pass 2: After the main pass, try to fit any deferred high-importance items.
        deferred: list[RetrievedSource] = []

        for candidate in candidates:
            # Dedup by source_id
            if candidate.source_id in seen_ids:
                continue

            # Per-chapter scene cap
            if candidate.source_type == "chapter_scene" and candidate.chapter_id is not None:
                count = chapter_scene_counts.get(candidate.chapter_id, 0)
                if count >= _MAX_CHAPTER_SCENES:
                    # "Lower-ranked duplicate scene" — skip it
                    continue
                chapter_scene_counts[candidate.chapter_id] = count + 1

            # Item budget check
            if len(items) >= _WRITER_BUDGET:
                break

            # Token budget estimate
            token_estimate = len(candidate.preview) * 2
            if estimated_tokens + token_estimate > _TOKEN_BUDGET_ESTIMATE:
                # Defer high-importance items for potential later inclusion
                if candidate.importance == "major":
                    deferred.append(candidate)
                continue

            seen_ids.add(candidate.source_id)
            estimated_tokens += token_estimate
            items.append(to_writer_context_item(candidate, reason="retrieved"))

        # Pass 2: Try to include deferred high-importance items
        for candidate in deferred:
            if len(items) >= _WRITER_BUDGET:
                break
            if candidate.source_id in seen_ids:
                continue
            token_estimate = len(candidate.preview) * 2
            if estimated_tokens + token_estimate > _TOKEN_BUDGET_ESTIMATE:
                continue
            seen_ids.add(candidate.source_id)
            estimated_tokens += token_estimate
            items.append(to_writer_context_item(candidate, reason="retrieved"))

        return items

    def _build_guard_constraints(
        self, guard_candidates: list[RetrievedSource]
    ) -> list[dict[str, Any]]:
        """Build guard constraints from guard-visibility sources.

        Guard constraints include name, status, and risk wording from
        the source title/preview.  They do NOT include hidden_truth in
        the writer context.
        """
        constraints: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for candidate in guard_candidates:
            if len(constraints) >= _GUARD_BUDGET:
                break
            if candidate.source_id in seen_ids:
                continue

            seen_ids.add(candidate.source_id)
            item = to_source_item(candidate, reason="guard_constraint")
            item["constraint"] = (
                f"本章不得提前确认或揭示‘{candidate.title}’对应的隐藏真相；"
                "请遵守该伏笔当前状态。"
            )
            constraints.append(item)

        return constraints

    def _build_source_items(
        self,
        writer_items: list[dict[str, Any]],
        guard_constraints: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build the combined source_items list.

        Combines writer_items and guard_constraints, deduplicating by
        source_id (writer items take precedence).
        """
        seen_ids: set[str] = set()
        combined: list[dict[str, Any]] = []

        for item in writer_items:
            sid = item["source_id"]
            if sid not in seen_ids:
                seen_ids.add(sid)
                combined.append({
                    key: item[key]
                    for key in (
                        "source_id",
                        "source_type",
                        "title",
                        "locator",
                        "preview",
                        "inclusion_reason",
                    )
                })

        for item in guard_constraints:
            sid = item["source_id"]
            if sid not in seen_ids:
                seen_ids.add(sid)
                combined.append({
                    key: item[key]
                    for key in (
                        "source_id",
                        "source_type",
                        "title",
                        "locator",
                        "preview",
                        "inclusion_reason",
                    )
                })

        return combined

    def _build_diagnostics(
        self,
        writer_candidates: list[RetrievedSource],
        guard_candidates: list[RetrievedSource],
        reranked_writer: list[RetrievedSource],
    ) -> dict[str, Any]:
        """Build diagnostics dict with raw scores and metadata.

        Only for debugging — never shown to the writer.
        """
        return {
            "collection_version": _COLLECTION_VERSION,
            "writer_candidates": [c.source_id for c in writer_candidates],
            "guard_candidates": [c.source_id for c in guard_candidates],
            "reranked_writer": [c.source_id for c in reranked_writer],
            "retrieval_status": "ok",
        }
