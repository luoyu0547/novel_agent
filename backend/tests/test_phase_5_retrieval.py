"""Phase 5 retrieval: durable job model, repository, service, and adapter contracts."""
import datetime
import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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


# ---------------------------------------------------------------------------
# Task 2: Model Studio and Qdrant adapter contract tests
# ---------------------------------------------------------------------------

from app.retrieval.contracts import (
    EmbeddingProvider,
    HybridEmbedding,
    RerankResult,
    Reranker,
    RetrievalUnavailable,
    VectorStore,
)
from app.retrieval.model_studio import ModelStudioClient
from app.retrieval.qdrant_store import QdrantVectorStore


def fake_settings(**overrides: Any) -> MagicMock:
    """Build a Settings-like object with sensible defaults for tests."""
    defaults = dict(
        MODEL_STUDIO_BASE_URL="https://model-studio.test",
        MODEL_STUDIO_API_KEY="test-key",
        MODEL_STUDIO_EMBEDDING_MODEL="text-embedding-v4",
        MODEL_STUDIO_RERANK_MODEL="qwen3-rerank",
        QDRANT_URL="http://127.0.0.1:6333",
        QDRANT_COLLECTION="novel-context-v1",
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


def client_returning(json_body: dict) -> ModelStudioClient:
    """Build a ModelStudioClient whose HTTP always returns *json_body*."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=json_body)

    return ModelStudioClient(
        settings=fake_settings(),
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


# -- Model Studio embedding tests ------------------------------------------


@pytest.mark.asyncio
async def test_model_studio_requests_dense_sparse_documents_and_query():
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"output": {"embeddings": [{
            "embedding": [0.1] * 1024,
            "sparse_embedding": {"indices": [7], "values": [0.8]},
        }]}})

    client = ModelStudioClient(
        settings=fake_settings(),
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await client.embed_documents(["沈砚发现账册"])
    await client.embed_query("军饷账册与沈砚")

    assert json.loads(captured[0].content)["parameters"] == {
        "dimension": 1024, "output_type": "dense&sparse", "text_type": "document"
    }
    assert json.loads(captured[1].content)["parameters"]["text_type"] == "query"


@pytest.mark.asyncio
async def test_model_studio_embed_documents_returns_hybrid_embeddings():
    client = client_returning({"output": {"embeddings": [
        {"embedding": [0.1] * 1024, "sparse_embedding": {"indices": [1, 5], "values": [0.3, 0.7]}},
        {"embedding": [0.2] * 1024, "sparse_embedding": {"indices": [2], "values": [0.9]}},
    ]}})
    result = await client.embed_documents(["文本一", "文本二"])
    assert len(result) == 2
    assert isinstance(result[0], HybridEmbedding)
    assert len(result[0].dense) == 1024
    assert result[0].sparse_indices == [1, 5]
    assert result[0].sparse_values == [0.3, 0.7]
    assert result[1].sparse_indices == [2]


@pytest.mark.asyncio
async def test_model_studio_embed_query_returns_single_hybrid():
    client = client_returning({"output": {"embeddings": [{
        "embedding": [0.3] * 1024,
        "sparse_embedding": {"indices": [10], "values": [0.5]},
    }]}})
    result = await client.embed_query("查询文本")
    assert isinstance(result, HybridEmbedding)
    assert len(result.dense) == 1024
    assert result.sparse_indices == [10]
    assert result.sparse_values == [0.5]


@pytest.mark.asyncio
async def test_model_studio_embed_documents_batches_over_ten():
    """When more than 10 texts are passed, the client should batch them."""
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        body = json.loads(request.content)
        n = len(body["input"]["texts"])
        embeddings = [
            {"embedding": [0.1] * 1024, "sparse_embedding": {"indices": [0], "values": [1.0]}}
            for _ in range(n)
        ]
        return httpx.Response(200, json={"output": {"embeddings": embeddings}})

    client = ModelStudioClient(
        settings=fake_settings(),
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await client.embed_documents([f"文本{i}" for i in range(25)])
    assert len(result) == 25
    assert call_count == 3  # 10 + 10 + 5


@pytest.mark.asyncio
async def test_model_studio_embed_validates_1024_dense():
    """If the API returns wrong dense dimension, raise RetrievalUnavailable."""
    client = client_returning({"output": {"embeddings": [{
        "embedding": [0.1] * 512,
        "sparse_embedding": {"indices": [0], "values": [1.0]},
    }]}})
    with pytest.raises(RetrievalUnavailable):
        await client.embed_query("bad dimension")


@pytest.mark.asyncio
async def test_model_studio_embed_wraps_http_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal"})

    client = ModelStudioClient(
        settings=fake_settings(),
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(RetrievalUnavailable, match="检索服务暂不可用"):
        await client.embed_query("触发错误")


@pytest.mark.asyncio
async def test_model_studio_embed_wraps_timeout():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    client = ModelStudioClient(
        settings=fake_settings(),
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(RetrievalUnavailable, match="检索服务暂不可用"):
        await client.embed_documents(["超时"])


@pytest.mark.asyncio
async def test_model_studio_embed_wraps_invalid_payload():
    """Non-JSON or malformed response should be wrapped."""
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    client = ModelStudioClient(
        settings=fake_settings(),
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(RetrievalUnavailable, match="检索服务暂不可用"):
        await client.embed_query("bad payload")


# -- Model Studio rerank tests ----------------------------------------------


@pytest.mark.asyncio
async def test_model_studio_rerank_uses_qwen3_result_indices():
    client = client_returning(
        {"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}]}
    )
    assert [item.index for item in await client.rerank("军饷", ["旧事", "账册"])] == [1, 0]


@pytest.mark.asyncio
async def test_model_studio_rerank_returns_scores():
    client = client_returning(
        {"results": [{"index": 0, "relevance_score": 0.95}, {"index": 1, "relevance_score": 0.3}]}
    )
    results = await client.rerank("查询", ["文档A", "文档B"])
    assert results[0].score == 0.95
    assert results[1].score == 0.3


@pytest.mark.asyncio
async def test_model_studio_rerank_wraps_http_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": "bad gateway"})

    client = ModelStudioClient(
        settings=fake_settings(),
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(RetrievalUnavailable, match="检索服务暂不可用"):
        await client.rerank("查询", ["文档"])


@pytest.mark.asyncio
async def test_model_studio_rerank_sends_correct_payload():
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"results": []})

    client = ModelStudioClient(
        settings=fake_settings(),
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await client.rerank("军饷", ["旧事", "账册"])
    body = json.loads(captured[0].content)
    assert body["model"] == "qwen3-rerank"
    assert body["query"] == "军饷"
    assert body["documents"] == ["旧事", "账册"]
    assert body["top_n"] == 2
    assert body["instruct"] == "Retrieve novel canon passages relevant to the current writing task."


# -- QdrantVectorStore tests (mocked AsyncQdrantClient) --------------------


@pytest.mark.asyncio
async def test_qdrant_ensure_collection_creates_when_absent():
    mock_client = AsyncMock()
    mock_client.collection_exists = AsyncMock(return_value=False)
    mock_client.create_collection = AsyncMock()

    store = QdrantVectorStore(settings=fake_settings(), client=mock_client)
    await store.ensure_collection()

    mock_client.collection_exists.assert_awaited_once_with("novel-context-v1")
    mock_client.create_collection.assert_awaited_once()


@pytest.mark.asyncio
async def test_qdrant_ensure_collection_skips_when_present():
    mock_client = AsyncMock()
    mock_client.collection_exists = AsyncMock(return_value=True)
    mock_client.create_collection = AsyncMock()

    store = QdrantVectorStore(settings=fake_settings(), client=mock_client)
    await store.ensure_collection()

    mock_client.create_collection.assert_not_awaited()


@pytest.mark.asyncio
async def test_qdrant_upsert_delegates_to_client():
    mock_client = AsyncMock()
    mock_client.upsert = AsyncMock()

    store = QdrantVectorStore(settings=fake_settings(), client=mock_client)
    points = [{"id": "1", "vector": {"dense": [0.1] * 1024}, "payload": {"text": "hello"}}]
    await store.upsert(points)

    mock_client.upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_qdrant_hybrid_search_builds_rrf_query():
    mock_client = AsyncMock()
    scored_point = MagicMock()
    scored_point.id = "point-1"
    scored_point.score = 0.95
    scored_point.payload = {"text": "匹配文本", "source_chapter": 3}
    mock_result = MagicMock()
    mock_result.points = [scored_point]
    mock_client.query_points = AsyncMock(return_value=mock_result)

    store = QdrantVectorStore(settings=fake_settings(), client=mock_client)
    query_emb = HybridEmbedding(
        dense=[0.1] * 1024, sparse_indices=[1, 5], sparse_values=[0.3, 0.7]
    )
    results = await store.hybrid_search(query_emb, tenant_key="1:2", limit=5)

    mock_client.query_points.assert_awaited_once()
    call_kwargs = mock_client.query_points.call_args[1]
    assert call_kwargs["collection_name"] == "novel-context-v1"
    assert call_kwargs["limit"] == 5
    assert call_kwargs["with_payload"] is True
    # Verify two prefetches
    assert len(call_kwargs["prefetch"]) == 2
    assert len(results) == 1


@pytest.mark.asyncio
async def test_qdrant_list_indexed_sources():
    mock_client = AsyncMock()
    mock_client.scroll = AsyncMock(return_value=([], None))

    store = QdrantVectorStore(settings=fake_settings(), client=mock_client)
    await store.list_indexed_sources("1:2")

    mock_client.scroll.assert_awaited_once()


@pytest.mark.asyncio
async def test_qdrant_delete_point_ids():
    mock_client = AsyncMock()
    mock_client.delete = AsyncMock()

    store = QdrantVectorStore(settings=fake_settings(), client=mock_client)
    await store.delete_point_ids(["id1", "id2"])

    mock_client.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_qdrant_delete_tenant():
    mock_client = AsyncMock()
    mock_client.delete = AsyncMock()

    store = QdrantVectorStore(settings=fake_settings(), client=mock_client)
    await store.delete_tenant("1:2")

    mock_client.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_qdrant_wraps_exceptions():
    mock_client = AsyncMock()
    mock_client.collection_exists = AsyncMock(side_effect=Exception("connection refused"))

    store = QdrantVectorStore(settings=fake_settings(), client=mock_client)
    with pytest.raises(RetrievalUnavailable, match="检索服务暂不可用"):
        await store.ensure_collection()


# -- Protocol conformance tests ---------------------------------------------


@pytest.mark.asyncio
async def test_model_studio_satisfies_embedding_provider_protocol():
    """ModelStudioClient should satisfy the EmbeddingProvider protocol."""
    client = client_returning({"output": {"embeddings": [{
        "embedding": [0.1] * 1024,
        "sparse_embedding": {"indices": [0], "values": [1.0]},
    }]}})
    # This is a structural check: the protocol methods exist with correct signatures
    assert hasattr(client, "embed_documents")
    assert hasattr(client, "embed_query")
    # Runtime type check
    def _accepts_provider(p: EmbeddingProvider) -> None: pass
    _accepts_provider(client)


@pytest.mark.asyncio
async def test_model_studio_satisfies_reranker_protocol():
    """ModelStudioClient should satisfy the Reranker protocol."""
    client = client_returning({"results": []})
    assert hasattr(client, "rerank")
    def _accepts_reranker(r: Reranker) -> None: pass
    _accepts_reranker(client)


@pytest.mark.asyncio
async def test_qdrant_satisfies_vector_store_protocol():
    """QdrantVectorStore should satisfy the VectorStore protocol."""
    mock_client = AsyncMock()
    store = QdrantVectorStore(settings=fake_settings(), client=mock_client)
    assert hasattr(store, "upsert")
    assert hasattr(store, "hybrid_search")
    assert hasattr(store, "list_indexed_sources")
    assert hasattr(store, "delete_point_ids")
    assert hasattr(store, "delete_tenant")
    assert hasattr(store, "ensure_collection")
    def _accepts_store(s: VectorStore) -> None: pass
    _accepts_store(store)
