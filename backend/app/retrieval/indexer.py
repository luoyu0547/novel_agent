"""Idempotent novel indexer for the retrieval subsystem.

Orchestrates the :class:`CanonicalSourceBuilder` with an
:class:`EmbeddingProvider` and :class:`VectorStore` to keep a novel's
vector index in sync with its canonical sources.

The sync algorithm:
1. Build current canonical sources via :class:`CanonicalSourceBuilder`.
2. Fetch existing indexed sources from the vector store.
3. Delete stale points (source gone or content hash changed) **before**
   upserting new/changed ones — this prevents deleting the replacement.
4. Embed only new/changed sources in batches of 10.
5. Upsert the new point records.

The worker calls ``delete_tenant()`` for purge operations, never ``sync()``
after a novel has been deleted.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.contracts import EmbeddingProvider, IndexedSource, VectorStore
from app.retrieval.source_builder import CanonicalSourceBuilder, RetrievalSource

logger = logging.getLogger(__name__)

_EMBED_BATCH_SIZE = 10


# ---------------------------------------------------------------------------
# IndexSyncResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndexSyncResult:
    """Result of a sync operation."""

    upserted: int = 0
    deleted: int = 0


# ---------------------------------------------------------------------------
# NovelIndexer
# ---------------------------------------------------------------------------


class NovelIndexer:
    """Idempotent indexer that syncs a novel's canonical sources to the
    vector store.

    Parameters
    ----------
    db:
        Async database session.
    embedder:
        An :class:`EmbeddingProvider` for computing hybrid embeddings.
    store:
        A :class:`VectorStore` for persisting and querying points.
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        embedder: EmbeddingProvider,
        store: VectorStore,
    ) -> None:
        self._db = db
        self._embedder = embedder
        self._store = store
        self._builder = CanonicalSourceBuilder(db)

    async def sync(self, novel_id: int, user_id: int) -> IndexSyncResult:
        """Synchronize the vector index for the given novel.

        Returns an :class:`IndexSyncResult` with counts of upserted and
        deleted points.
        """
        tenant_key = f"{user_id}:{novel_id}"

        # Step 1: Build current canonical sources
        sources = await self._builder.build(novel_id, user_id)
        current_by_source: dict[str, RetrievalSource] = {
            s.source_id: s for s in sources
        }

        # Step 2: Fetch existing indexed sources from the store
        old_items = await self._store.list_indexed_sources(tenant_key)
        old_by_source: dict[str, IndexedSource] = {
            item.source_id: item for item in old_items
        }

        # Step 3: Determine stale points to delete (BEFORE upsert)
        to_delete: list[str] = []
        for source_id, old in old_by_source.items():
            if source_id not in current_by_source:
                # Source is gone
                to_delete.append(old.point_id)
            elif old.content_hash != current_by_source[source_id].content_hash:
                # Content changed — delete old point, new one will be upserted
                to_delete.append(old.point_id)

        if to_delete:
            await self._store.delete_point_ids(to_delete)

        # Step 4: Determine new/changed sources to upsert
        to_upsert: list[RetrievalSource] = []
        for source in sources:
            if source.source_id not in old_by_source:
                # New source
                to_upsert.append(source)
            elif old_by_source[source.source_id].content_hash != source.content_hash:
                # Changed source (old point already deleted in step 3)
                to_upsert.append(source)

        # Step 5: Embed and upsert in batches
        upserted = 0
        for batch_start in range(0, len(to_upsert), _EMBED_BATCH_SIZE):
            batch = to_upsert[batch_start:batch_start + _EMBED_BATCH_SIZE]
            texts = [s.text for s in batch]
            embeddings = await self._embedder.embed_documents(texts)

            points: list[dict] = []
            for source, embedding in zip(batch, embeddings):
                points.append({
                    "id": source.point_id,
                    "vector": {
                        "dense": embedding.dense,
                        "sparse": {
                            "indices": embedding.sparse_indices,
                            "values": embedding.sparse_values,
                        },
                    },
                    "payload": {
                        "tenant_key": source.tenant_key,
                        "source_id": source.source_id,
                        "source_type": source.source_type,
                        "source_record_id": source.source_record_id,
                        "chapter_id": source.chapter_id,
                        "title": source.title,
                        "text": source.text,
                        "preview": source.preview,
                        "visibility": source.visibility,
                        "locator": source.locator,
                        "content_hash": source.content_hash,
                        "importance": source.importance,
                    },
                })

            await self._store.upsert(points)
            upserted += len(points)

        return IndexSyncResult(upserted=upserted, deleted=len(to_delete))
