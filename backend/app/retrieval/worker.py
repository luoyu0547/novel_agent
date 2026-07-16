"""Background worker for processing retrieval index jobs.

Consumes jobs from the ``retrieval_index_jobs`` table via
:class:`RetrievalIndexRepo.claim_next`, dispatches to
:class:`NovelIndexer.sync` or :meth:`NovelIndexer.purge`, and commits
each transition separately.

Run with::

    python -m app.retrieval.worker
"""
from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.contracts import RetrievalUnavailable
from app.repositories.retrieval_index_repo import RetrievalIndexRepo

logger = logging.getLogger(__name__)


class RetrievalWorker:
    """Process retrieval index jobs one at a time.

    Parameters
    ----------
    session_factory:
        A callable returning an async context manager that yields an
        :class:`AsyncSession`.  In production this is
        ``async_session_factory`` from :mod:`app.core.database`.
    indexer:
        An object with ``sync(novel_id, user_id)`` and
        ``purge(tenant_key)`` async methods (e.g.
        :class:`~app.retrieval.indexer.NovelIndexer`).
    """

    def __init__(
        self,
        *,
        session_factory: Callable,
        indexer,
    ) -> None:
        self._session_factory = session_factory
        self._indexer = indexer

    async def run_once(self) -> bool:
        """Claim and process a single job.

        Returns ``True`` if a job was claimed (whether it succeeded or
        failed), ``False`` if no job was available.
        """
        async with self._session_factory() as db:
            repo = RetrievalIndexRepo(db)
            job = await repo.claim_next(datetime.datetime.now())
            if job is None:
                return False
            await db.commit()

            try:
                if job.operation == "purge":
                    await self._indexer.purge(job.tenant_key)
                else:
                    # sync or rebuild — both use the same sync path
                    user_id = int(job.tenant_key.split(":", maxsplit=1)[0])
                    await self._indexer.sync(job.novel_id, user_id)
            except RetrievalUnavailable as exc:
                await repo.retry(job, str(exc))
            except Exception:
                logger.exception("Retrieval index job %s failed", job.id)
                await repo.retry(job, "索引任务失败")
            else:
                await repo.complete(job)

            await db.commit()
            return True


async def main() -> None:
    """Main loop: repeatedly call :meth:`run_once`, sleeping 1 s when idle."""
    from app.core.database import async_session_factory
    from app.retrieval.indexer import NovelIndexer
    from app.retrieval.model_studio import ModelStudioClient
    from app.retrieval.qdrant_store import QdrantVectorStore
    from app.core.config import settings

    embedder = ModelStudioClient(settings=settings)
    store = QdrantVectorStore(settings=settings)

    class _IndexerAdapter:
        """Adapts the per-session indexer to the worker's interface.

        The worker creates a fresh DB session per ``run_once`` call for
        job claiming, but the indexer also needs its own session for
        source building.  This adapter opens a second session for each
        ``sync`` call; ``purge`` only needs the store (no DB access).
        """

        def __init__(self, embedder, store):
            self._embedder = embedder
            self._store = store

        async def sync(self, novel_id: int, user_id: int):
            async with async_session_factory() as db:
                idx = NovelIndexer(db, embedder=self._embedder, store=self._store)
                return await idx.sync(novel_id, user_id)

        async def purge(self, tenant_key: str):
            await self._store.delete_tenant(tenant_key)

    adapter = _IndexerAdapter(embedder, store)
    worker = RetrievalWorker(session_factory=async_session_factory, indexer=adapter)

    logger.info("Retrieval worker started")
    while True:
        claimed = await worker.run_once()
        if not claimed:
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
