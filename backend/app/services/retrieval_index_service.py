"""Service for retrieval index job lifecycle management."""
import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval import RetrievalIndexJob, ACTIVE_STATUSES
from app.repositories.retrieval_index_repo import RetrievalIndexRepo


class RetrievalIndexService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = RetrievalIndexRepo(db)

    async def enqueue_sync(
        self, novel_id: int, user_id: int
    ) -> RetrievalIndexJob:
        """Enqueue a sync operation. Returns existing active job if one exists."""
        tenant_key = f"{user_id}:{novel_id}"
        existing = await self.repo.find_active_by_tenant_key(tenant_key)
        if existing and existing.operation in ("sync", "rebuild"):
            return existing
        job = RetrievalIndexJob(
            novel_id=novel_id,
            tenant_key=tenant_key,
            operation="sync",
            status="pending",
            attempt_count=0,
            next_attempt_at=datetime.datetime.now(),
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def enqueue_purge(
        self, novel_id: int, user_id: int
    ) -> RetrievalIndexJob:
        """Enqueue a purge operation. Returns existing active purge if one exists."""
        tenant_key = f"{user_id}:{novel_id}"
        existing = await self.repo.find_active_purge_by_tenant_key(tenant_key)
        if existing:
            return existing
        job = RetrievalIndexJob(
            novel_id=novel_id,
            tenant_key=tenant_key,
            operation="purge",
            status="pending",
            attempt_count=0,
            next_attempt_at=datetime.datetime.now(),
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def request_rebuild(
        self, novel_id: int, user_id: int
    ) -> RetrievalIndexJob:
        """Request a rebuild. Deduplicates against active sync/rebuild jobs."""
        tenant_key = f"{user_id}:{novel_id}"
        existing = await self.repo.find_active_by_tenant_key(tenant_key)
        if existing and existing.operation in ("sync", "rebuild"):
            return existing
        job = RetrievalIndexJob(
            novel_id=novel_id,
            tenant_key=tenant_key,
            operation="rebuild",
            status="pending",
            attempt_count=0,
            next_attempt_at=datetime.datetime.now(),
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def status(
        self, novel_id: int, user_id: int
    ) -> Optional[RetrievalIndexJob]:
        """Return the latest job for a novel, or None if no jobs exist."""
        tenant_key = f"{user_id}:{novel_id}"
        return await self.repo.find_latest_by_tenant_key(tenant_key)
