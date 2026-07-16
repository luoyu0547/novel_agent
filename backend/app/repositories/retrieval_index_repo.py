"""Repository for RetrievalIndexJob persistence and queries."""
import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval import RetrievalIndexJob, ACTIVE_STATUSES


class RetrievalIndexRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_active_by_tenant_key(
        self, tenant_key: str
    ) -> Optional[RetrievalIndexJob]:
        """Return an active (pending/running/retry_wait) job for the given tenant key."""
        stmt = (
            select(RetrievalIndexJob)
            .where(
                RetrievalIndexJob.tenant_key == tenant_key,
                RetrievalIndexJob.status.in_(ACTIVE_STATUSES),
            )
            .order_by(RetrievalIndexJob.requested_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_active_purge_by_tenant_key(
        self, tenant_key: str
    ) -> Optional[RetrievalIndexJob]:
        """Return an active purge job for the given tenant key."""
        stmt = (
            select(RetrievalIndexJob)
            .where(
                RetrievalIndexJob.tenant_key == tenant_key,
                RetrievalIndexJob.operation == "purge",
                RetrievalIndexJob.status.in_(ACTIVE_STATUSES),
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_latest_by_tenant_key(
        self, tenant_key: str
    ) -> Optional[RetrievalIndexJob]:
        """Return the latest job (any status) for the given tenant key."""
        stmt = (
            select(RetrievalIndexJob)
            .where(RetrievalIndexJob.tenant_key == tenant_key)
            .order_by(RetrievalIndexJob.requested_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def claim_next(self, now: datetime.datetime) -> Optional[RetrievalIndexJob]:
        """Claim the next eligible job for processing.

        Selects a pending or retry_wait job whose next_attempt_at is due,
        ordered by requested_at. Sets status to running with a 5-minute lease.
        Uses SELECT ... FOR UPDATE SKIP LOCKED for safe concurrent claiming.
        """
        stmt = (
            select(RetrievalIndexJob)
            .where(
                RetrievalIndexJob.status.in_(("pending", "retry_wait")),
                RetrievalIndexJob.next_attempt_at <= now,
            )
            .order_by(RetrievalIndexJob.requested_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = (await self.db.execute(stmt)).scalar_one_or_none()
        if job is None:
            return None
        job.status = "running"
        job.lease_expires_at = now + datetime.timedelta(minutes=5)
        job.started_at = now
        await self.db.flush()
        return job

    async def complete(self, job: RetrievalIndexJob) -> None:
        """Mark a job as completed."""
        job.status = "completed"
        job.lease_expires_at = None
        await self.db.flush()

    async def retry(self, job: RetrievalIndexJob, error: str) -> None:
        """Retry a running job.

        Increments attempt_count, calculates exponential backoff delay,
        and transitions to retry_wait. After 5 attempts, transitions to
        failed instead.
        """
        job.attempt_count += 1
        job.last_error = error
        job.lease_expires_at = None
        job.started_at = None

        if job.attempt_count >= 5:
            job.status = "failed"
        else:
            delay_seconds = min(300, 2 ** job.attempt_count)
            job.status = "retry_wait"
            job.next_attempt_at = datetime.datetime.now() + datetime.timedelta(
                seconds=delay_seconds
            )
        await self.db.flush()

    async def fail(self, job: RetrievalIndexJob, error: str) -> None:
        """Mark a job as failed immediately."""
        job.status = "failed"
        job.last_error = error
        job.lease_expires_at = None
        await self.db.flush()
