"""Qdrant vector store adapter for hybrid search.

Wraps ``AsyncQdrantClient`` and normalizes all Qdrant exceptions into
:class:`RetrievalUnavailable`.  No caller should ever see a Qdrant-native
exception or internal detail.
"""
from __future__ import annotations

import logging
from typing import Any

from qdrant_client import AsyncQdrantClient, models

from app.retrieval.contracts import (
    HybridEmbedding,
    IndexedSource,
    RetrievedSource,
    RetrievalUnavailable,
)

logger = logging.getLogger(__name__)

_DENSE_VECTOR_NAME = "dense"
_SPARSE_VECTOR_NAME = "sparse"


class QdrantVectorStore:
    """Async Qdrant adapter with hybrid (dense + sparse RRF) search.

    Parameters
    ----------
    settings:
        Object with ``QDRANT_URL`` and ``QDRANT_COLLECTION`` attributes.
    client:
        A pre-configured ``AsyncQdrantClient``.  Callers may inject a mock
        for testing; production code should pass ``None`` to have one
        created from *settings*.
    """

    def __init__(self, settings: Any, client: AsyncQdrantClient | None = None) -> None:
        self._url = settings.QDRANT_URL
        self._collection = settings.QDRANT_COLLECTION
        self._client = client or AsyncQdrantClient(url=self._url)

    # -- Collection management -----------------------------------------------

    async def ensure_collection(self) -> None:
        """Create the collection with dense/sparse vectors if absent."""
        try:
            exists = await self._client.collection_exists(self._collection)
            if exists:
                return
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config={
                    _DENSE_VECTOR_NAME: models.VectorParams(
                        size=1024,
                        distance=models.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    _SPARSE_VECTOR_NAME: models.SparseVectorParams(),
                },
            )
            # Create payload indexes for efficient filtering
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="tenant_key",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="chapter_id",
                field_schema=models.PayloadSchemaType.INTEGER,
            )
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="source_type",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="source_record_id",
                field_schema=models.PayloadSchemaType.INTEGER,
            )
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="visibility",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="index_version",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            if isinstance(exc, RetrievalUnavailable):
                raise
            logger.warning("Qdrant ensure_collection failed: %s", type(exc).__name__)
            raise RetrievalUnavailable() from exc

    # -- Write operations ----------------------------------------------------

    async def upsert(self, points: list[dict]) -> None:
        """Upsert a list of point dicts into the collection."""
        try:
            await self._client.upsert(collection_name=self._collection, points=points)
        except Exception as exc:
            if isinstance(exc, RetrievalUnavailable):
                raise
            logger.warning("Qdrant upsert failed: %s", type(exc).__name__)
            raise RetrievalUnavailable() from exc

    # -- Read operations -----------------------------------------------------

    async def hybrid_search(
        self,
        query: HybridEmbedding,
        tenant_key: str,
        visibility: str = "default",
        limit: int = 10,
        dense_limit: int = 24,
        sparse_limit: int = 24,
    ) -> list[RetrievedSource]:
        """Run a hybrid dense + sparse RRF search scoped to *tenant_key*.

        When *visibility* is ``"writer"``, results include sources with
        visibility ``"default"`` only.  When ``"guard"``, only sources
        with visibility ``"guard"`` are returned.
        """
        must_conditions = [
            models.FieldCondition(
                key="tenant_key",
                match=models.MatchValue(value=tenant_key),
            )
        ]
        # Map the service-level visibility label to the stored payload value
        if visibility == "writer":
            must_conditions.append(
                models.FieldCondition(
                    key="visibility",
                    match=models.MatchValue(value="default"),
                )
            )
        elif visibility == "guard":
            must_conditions.append(
                models.FieldCondition(
                    key="visibility",
                    match=models.MatchValue(value="guard"),
                )
            )

        tenant_filter = models.Filter(must=must_conditions)
        try:
            result = await self._client.query_points(
                collection_name=self._collection,
                prefetch=[
                    models.Prefetch(
                        query=query.dense,
                        using=_DENSE_VECTOR_NAME,
                        filter=tenant_filter,
                        limit=dense_limit,
                    ),
                    models.Prefetch(
                        query=models.SparseVector(
                            indices=query.sparse_indices,
                            values=query.sparse_values,
                        ),
                        using=_SPARSE_VECTOR_NAME,
                        filter=tenant_filter,
                        limit=sparse_limit,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
                with_payload=True,
            )
            return [
                RetrievedSource(
                    source_id=payload.get("source_id", ""),
                    source_type=payload.get("source_type", ""),
                    title=payload.get("title", ""),
                    preview=payload.get("preview", ""),
                    locator=payload.get("locator", {}),
                    visibility=payload.get("visibility", "default"),
                    chapter_id=payload.get("chapter_id"),
                    importance=payload.get("importance", "minor"),
                )
                for point in result.points
                if (payload := point.payload or {})
            ]
        except Exception as exc:
            if isinstance(exc, RetrievalUnavailable):
                raise
            logger.warning("Qdrant hybrid_search failed: %s", type(exc).__name__)
            raise RetrievalUnavailable() from exc

    async def list_indexed_sources(self, tenant_key: str) -> list[IndexedSource]:
        """Return indexed source records for a tenant with point_id, source_id, content_hash."""
        try:
            sources: list[IndexedSource] = []
            offset = None
            while True:
                records, offset = await self._client.scroll(
                    collection_name=self._collection,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="tenant_key",
                                match=models.MatchValue(value=tenant_key),
                            )
                        ]
                    ),
                    with_payload=["source_id", "content_hash"],
                    limit=100,
                    offset=offset,
                )
                for record in records:
                    payload = record.payload or {}
                    sources.append(IndexedSource(
                        point_id=str(record.id),
                        source_id=payload.get("source_id", ""),
                        content_hash=payload.get("content_hash", ""),
                    ))
                if offset is None:
                    break
            return sources
        except Exception as exc:
            if isinstance(exc, RetrievalUnavailable):
                raise
            logger.warning("Qdrant list_indexed_sources failed: %s", type(exc).__name__)
            raise RetrievalUnavailable() from exc

    # -- Delete operations ---------------------------------------------------

    async def delete_point_ids(self, ids: list[str]) -> None:
        """Delete points by their IDs."""
        try:
            await self._client.delete(
                collection_name=self._collection,
                points_selector=models.PointIdsList(points=ids),
            )
        except Exception as exc:
            if isinstance(exc, RetrievalUnavailable):
                raise
            logger.warning("Qdrant delete_point_ids failed: %s", type(exc).__name__)
            raise RetrievalUnavailable() from exc

    async def delete_tenant(self, tenant_key: str) -> None:
        """Delete all points belonging to a tenant."""
        try:
            await self._client.delete(
                collection_name=self._collection,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="tenant_key",
                                match=models.MatchValue(value=tenant_key),
                            )
                        ]
                    )
                ),
            )
        except Exception as exc:
            if isinstance(exc, RetrievalUnavailable):
                raise
            logger.warning("Qdrant delete_tenant failed: %s", type(exc).__name__)
            raise RetrievalUnavailable() from exc
