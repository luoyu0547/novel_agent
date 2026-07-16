"""Phase 5 retrieval: durable job model, repository, and service."""
import datetime

import pytest

from app.models.novel import Novel
from app.models.retrieval import RetrievalIndexJob
from app.models.user import User
from app.repositories.retrieval_index_repo import RetrievalIndexRepo
from app.services.retrieval_index_service import RetrievalIndexService


async def make_user_and_novel(db):
    user = User(username="retrieval_user", hashed_password="hash")
    db.add(user)
    await db.flush()
    novel = Novel(user_id=user.id, title="检索测试小说")
    db.add(novel)
    await db.commit()
    return user, novel


@pytest.mark.asyncio
async def test_retrieval_job_dedupes_sync_and_leases_then_completes(db):
    user, novel = await make_user_and_novel(db)
    service = RetrievalIndexService(db)
    first = await service.enqueue_sync(novel.id, user.id)
    second = await service.enqueue_sync(novel.id, user.id)

    assert second.id == first.id
    claimed = await service.repo.claim_next(datetime.datetime.now())
    assert claimed.status == "running"
    assert claimed.lease_expires_at is not None

    await service.repo.complete(claimed)
    assert (await service.status(novel.id, user.id)).status == "completed"


@pytest.mark.asyncio
async def test_purge_job_survives_novel_delete_shape(db):
    user, novel = await make_user_and_novel(db)
    job = await RetrievalIndexService(db).enqueue_purge(novel.id, user.id)
    assert job.novel_id == novel.id
    assert job.tenant_key == f"{user.id}:{novel.id}"
    assert job.operation == "purge"


@pytest.mark.asyncio
async def test_enqueue_sync_creates_pending_job(db):
    user, novel = await make_user_and_novel(db)
    service = RetrievalIndexService(db)
    job = await service.enqueue_sync(novel.id, user.id)
    assert job.operation == "sync"
    assert job.status == "pending"
    assert job.novel_id == novel.id
    assert job.tenant_key == f"{user.id}:{novel.id}"
    assert job.attempt_count == 0
    assert job.next_attempt_at is not None


@pytest.mark.asyncio
async def test_request_rebuild_dedupes_against_active_sync(db):
    user, novel = await make_user_and_novel(db)
    service = RetrievalIndexService(db)
    sync_job = await service.enqueue_sync(novel.id, user.id)
    rebuild_job = await service.request_rebuild(novel.id, user.id)
    # rebuild should return the existing active sync job (deduplication)
    assert rebuild_job.id == sync_job.id


@pytest.mark.asyncio
async def test_request_rebuild_creates_new_when_completed(db):
    user, novel = await make_user_and_novel(db)
    service = RetrievalIndexService(db)
    sync_job = await service.enqueue_sync(novel.id, user.id)
    # complete the sync job
    claimed = await service.repo.claim_next(datetime.datetime.now())
    await service.repo.complete(claimed)
    # now request rebuild — should create a new job
    rebuild_job = await service.request_rebuild(novel.id, user.id)
    assert rebuild_job.id != sync_job.id
    assert rebuild_job.operation == "rebuild"


@pytest.mark.asyncio
async def test_claim_next_returns_none_when_no_jobs(db):
    repo = RetrievalIndexRepo(db)
    result = await repo.claim_next(datetime.datetime.now())
    assert result is None


@pytest.mark.asyncio
async def test_claim_next_skips_future_next_attempt_at(db):
    user, novel = await make_user_and_novel(db)
    service = RetrievalIndexService(db)
    job = await service.enqueue_sync(novel.id, user.id)
    # set next_attempt_at far in the future
    job.next_attempt_at = datetime.datetime.now() + datetime.timedelta(hours=1)
    await db.commit()
    claimed = await service.repo.claim_next(datetime.datetime.now())
    assert claimed is None


@pytest.mark.asyncio
async def test_retry_increments_attempts_and_transitions(db):
    user, novel = await make_user_and_novel(db)
    service = RetrievalIndexService(db)
    job = await service.enqueue_sync(novel.id, user.id)
    claimed = await service.repo.claim_next(datetime.datetime.now())
    assert claimed.status == "running"

    await service.repo.retry(claimed, "transient error")
    assert claimed.status == "retry_wait"
    assert claimed.attempt_count == 1
    assert claimed.last_error == "transient error"
    assert claimed.lease_expires_at is None
    assert claimed.next_attempt_at is not None


@pytest.mark.asyncio
async def test_retry_fails_after_five_attempts(db):
    user, novel = await make_user_and_novel(db)
    service = RetrievalIndexService(db)
    job = await service.enqueue_sync(novel.id, user.id)
    claimed = await service.repo.claim_next(datetime.datetime.now())

    for i in range(4):
        await service.repo.retry(claimed, f"error {i}")
        # re-claim to set it running again
        claimed.next_attempt_at = datetime.datetime.now() - datetime.timedelta(seconds=1)
        await db.commit()
        claimed = await service.repo.claim_next(datetime.datetime.now())

    # 5th retry should transition to failed
    await service.repo.retry(claimed, "final error")
    assert claimed.status == "failed"
    assert claimed.attempt_count == 5


@pytest.mark.asyncio
async def test_fail_transitions_immediately(db):
    user, novel = await make_user_and_novel(db)
    service = RetrievalIndexService(db)
    job = await service.enqueue_sync(novel.id, user.id)
    claimed = await service.repo.claim_next(datetime.datetime.now())

    await service.repo.fail(claimed, "fatal error")
    assert claimed.status == "failed"
    assert claimed.last_error == "fatal error"


@pytest.mark.asyncio
async def test_status_returns_none_when_no_jobs(db):
    user, novel = await make_user_and_novel(db)
    service = RetrievalIndexService(db)
    result = await service.status(novel.id, user.id)
    assert result is None


@pytest.mark.asyncio
async def test_enqueue_purge_creates_new_even_if_sync_active(db):
    user, novel = await make_user_and_novel(db)
    service = RetrievalIndexService(db)
    sync_job = await service.enqueue_sync(novel.id, user.id)
    purge_job = await service.enqueue_purge(novel.id, user.id)
    assert purge_job.id != sync_job.id
    assert purge_job.operation == "purge"


@pytest.mark.asyncio
async def test_enqueue_purge_dedupes_existing_purge(db):
    user, novel = await make_user_and_novel(db)
    service = RetrievalIndexService(db)
    first_purge = await service.enqueue_purge(novel.id, user.id)
    second_purge = await service.enqueue_purge(novel.id, user.id)
    assert second_purge.id == first_purge.id
