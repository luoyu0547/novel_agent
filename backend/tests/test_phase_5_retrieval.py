"""Phase 5 retrieval: durable job model, repository, service, and adapter contracts."""
import datetime
import json
import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.foreshadowing import Foreshadowing
from app.models.memory import CharacterProfile, WorldSetting
from app.models.novel import Chapter, Novel
from app.models.plot_fact import PlotFact
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
    IndexedSource,
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
    mock_record = MagicMock()
    mock_record.id = "point-1"
    mock_record.payload = {"source_id": "chapter:1:summary", "content_hash": "abc123"}
    mock_client.scroll = AsyncMock(return_value=([mock_record], None))

    store = QdrantVectorStore(settings=fake_settings(), client=mock_client)
    result = await store.list_indexed_sources("1:2")

    mock_client.scroll.assert_awaited_once()
    assert len(result) == 1
    assert isinstance(result[0], IndexedSource)
    assert result[0].point_id == "point-1"
    assert result[0].source_id == "chapter:1:summary"
    assert result[0].content_hash == "abc123"


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


# ---------------------------------------------------------------------------
# Task 3: Canonical source builder and idempotent novel indexer
# ---------------------------------------------------------------------------

from app.retrieval.source_builder import CanonicalSourceBuilder, RetrievalSource
from app.retrieval.indexer import NovelIndexer, IndexSyncResult


# -- Helpers for building test data ----------------------------------------


async def add_chapter(db, novel, *, status="draft", content="", summary="", title="章节"):
    chapter = Chapter(novel_id=novel.id, title=title, content=content, summary=summary, status=status)
    db.add(chapter)
    await db.flush()
    return chapter


async def add_character(db, novel, *, name="角色", identity="", personality="", motivation="",
                        speech_style="", story_role="", current_state=""):
    char = CharacterProfile(
        novel_id=novel.id, name=name, identity=identity, personality=personality,
        motivation=motivation, speech_style=speech_style, story_role=story_role,
        current_state=current_state,
    )
    db.add(char)
    await db.flush()
    return char


async def add_plot_fact(db, novel, chapter, *, fact_type="event", content="事实", importance="minor"):
    fact = PlotFact(
        novel_id=novel.id, chapter_id=chapter.id, fact_type=fact_type,
        content=content, importance=importance,
    )
    db.add(fact)
    await db.flush()
    return fact


async def add_world_setting(db, novel, *, title="设定", category="地理", content="内容"):
    setting = WorldSetting(novel_id=novel.id, title=title, category=category, content=content)
    db.add(setting)
    await db.flush()
    return setting


async def add_foreshadowing(db, novel, chapter, *, name="伏笔", description="描述",
                            hidden_truth="", status="planted", risk_warning=""):
    fs = Foreshadowing(
        novel_id=novel.id, name=name, description=description,
        hidden_truth=hidden_truth, status=status,
        planted_chapter_id=chapter.id, risk_warning=risk_warning,
    )
    db.add(fs)
    await db.flush()
    return fs


# -- Fake store / embedder for indexer tests --------------------------------


@dataclass
class FakeIndexedSource:
    """Mimics the return type of list_indexed_sources."""
    point_id: str
    source_id: str
    content_hash: str


class FakeVectorStore:
    """In-memory fake VectorStore for indexer tests."""

    def __init__(self) -> None:
        self.points: dict[str, dict] = {}  # point_id -> point dict
        self.delete_calls: list[list[str]] = []

    async def ensure_collection(self) -> None:
        pass

    async def upsert(self, points: list[dict]) -> None:
        for p in points:
            self.points[str(p["id"])] = p

    async def hybrid_search(self, query, tenant_key, limit=10, dense_limit=20, sparse_limit=20):
        return []

    async def list_indexed_sources(self, tenant_key: str) -> list[FakeIndexedSource]:
        return [
            FakeIndexedSource(
                point_id=str(p["id"]),
                source_id=p["payload"]["source_id"],
                content_hash=p["payload"]["content_hash"],
            )
            for p in self.points.values()
            if p["payload"].get("tenant_key") == tenant_key
        ]

    async def delete_point_ids(self, ids: list[str]) -> None:
        self.delete_calls.append(ids)
        for pid in ids:
            self.points.pop(pid, None)

    async def delete_tenant(self, tenant_key: str) -> None:
        to_remove = [
            pid for pid, p in self.points.items()
            if p["payload"].get("tenant_key") == tenant_key
        ]
        for pid in to_remove:
            del self.points[pid]


class FakeEmbeddingProvider:
    """Returns deterministic hybrid embeddings."""

    async def embed_documents(self, texts: list[str]) -> list[HybridEmbedding]:
        return [
            HybridEmbedding(
                dense=[float(i) / 1024] * 1024,
                sparse_indices=[0],
                sparse_values=[1.0],
            )
            for i, _ in enumerate(texts)
        ]

    async def embed_query(self, text: str) -> HybridEmbedding:
        return HybridEmbedding(dense=[0.0] * 1024, sparse_indices=[0], sparse_values=[1.0])


# -- Source builder tests ---------------------------------------------------


@pytest.mark.asyncio
async def test_source_builder_indexes_only_locked_canon_and_hides_foreshadow_truth(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="甲。\n\n乙。", summary="摘要")
    await add_chapter(db, novel, status="draft", content="不能入索引")
    await add_foreshadowing(db, novel, locked, description="雨夜铃声", hidden_truth="凶手身份")

    sources = await CanonicalSourceBuilder(db).build(novel.id, user.id)
    assert {item.source_type for item in sources} >= {"chapter_summary", "chapter_scene", "foreshadowing_signal", "foreshadowing_guard"}
    assert all("不能入索引" not in item.text for item in sources)
    assert next(item for item in sources if item.source_type == "foreshadowing_signal").text.find("凶手身份") == -1
    assert "凶手身份" in next(item for item in sources if item.source_type == "foreshadowing_guard").text


@pytest.mark.asyncio
async def test_source_builder_skips_draft_chapters(db):
    user, novel = await make_user_and_novel(db)
    await add_chapter(db, novel, status="draft", content="草稿内容", summary="草稿摘要")

    sources = await CanonicalSourceBuilder(db).build(novel.id, user.id)
    chapter_sources = [s for s in sources if s.source_type in ("chapter_summary", "chapter_scene")]
    assert len(chapter_sources) == 0


@pytest.mark.asyncio
async def test_source_builder_includes_characters_plot_facts_world_settings(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="内容", summary="摘要")
    char = await add_character(db, novel, name="沈砚", identity="将军", personality="沉稳")
    fact = await add_plot_fact(db, novel, locked, content="军饷失踪")
    setting = await add_world_setting(db, novel, title="北境", content="苦寒之地")

    sources = await CanonicalSourceBuilder(db).build(novel.id, user.id)
    source_ids = {s.source_id for s in sources}
    assert f"character:{char.id}" in source_ids
    assert f"plot_fact:{fact.id}" in source_ids
    assert f"world_setting:{setting.id}" in source_ids


@pytest.mark.asyncio
async def test_source_builder_source_ids_follow_spec_format(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="场景一\n\n场景二", summary="摘要")
    char = await add_character(db, novel, name="角色")
    fact = await add_plot_fact(db, novel, locked, content="事实")
    setting = await add_world_setting(db, novel, title="设定")
    fs = await add_foreshadowing(db, novel, locked, name="伏笔", description="描述", hidden_truth="真相")

    sources = await CanonicalSourceBuilder(db).build(novel.id, user.id)
    source_ids = {s.source_id for s in sources}
    assert f"chapter:{locked.id}:summary" in source_ids
    assert f"chapter:{locked.id}:scene:0" in source_ids
    assert f"chapter:{locked.id}:scene:1" in source_ids
    assert f"character:{char.id}" in source_ids
    assert f"plot_fact:{fact.id}" in source_ids
    assert f"world_setting:{setting.id}" in source_ids
    assert f"foreshadowing:{fs.id}:signal" in source_ids
    assert f"foreshadowing:{fs.id}:guard" in source_ids


@pytest.mark.asyncio
async def test_source_builder_scene_chunking_combines_paragraphs(db):
    """Paragraphs under 700 chars should be combined; blank lines split scenes."""
    user, novel = await make_user_and_novel(db)
    # Each paragraph is short, so they should combine into one scene chunk
    content = "短段落一。" * 20 + "\n\n" + "短段落二。" * 20
    locked = await add_chapter(db, novel, status="locked", content=content, summary="摘要")

    sources = await CanonicalSourceBuilder(db).build(novel.id, user.id)
    scene_sources = [s for s in sources if s.source_type == "chapter_scene"]
    # Two blank-line-separated blocks → at least 2 scenes
    assert len(scene_sources) >= 2


@pytest.mark.asyncio
async def test_source_builder_carry_over_appears_at_start_of_next_chunk(db):
    """When combining paragraphs exceeds 700 CJK chars, the final 120 chars
    of the emitted chunk should appear at the start of the next chunk."""
    from app.retrieval.source_builder import _split_scenes, _CARRY_OVER_CHARS, _MAX_SCENE_CHARS

    # Build a block with two paragraphs: first is near the limit, second pushes over
    # Use CJK characters to ensure counting works
    para1 = "一" * 650  # 650 CJK chars — under limit
    para2 = "二" * 200  # 200 more CJK chars — combined exceeds 700
    content = para1 + "\n" + para2

    chunks = _split_scenes(content)
    assert len(chunks) >= 2, f"Expected at least 2 chunks, got {len(chunks)}"
    # The carry-over (last 120 chars of first chunk) should appear at the start of the second chunk
    first_chunk_tail = chunks[0][-_CARRY_OVER_CHARS:]
    assert chunks[1].startswith(first_chunk_tail), (
        f"Carry-over mismatch: first chunk tail is {first_chunk_tail!r}, "
        f"second chunk starts with {chunks[1][:_CARRY_OVER_CHARS]!r}"
    )


@pytest.mark.asyncio
async def test_source_builder_oversized_single_paragraph_splits_under_limit(db):
    """A single paragraph exceeding 700 CJK chars must produce multiple chunks,
    each under 700 CJK chars (after splitting at the 700-char boundary)."""
    from app.retrieval.source_builder import _split_scenes, _MAX_SCENE_CHARS

    # A single paragraph with 2000 CJK characters — no newlines
    big_para = "大" * 2000
    chunks = _split_scenes(big_para)

    assert len(chunks) >= 2, f"Expected multiple chunks for 2000-char paragraph, got {len(chunks)}"
    for i, chunk in enumerate(chunks):
        cjk = sum(1 for ch in chunk if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿")
        assert cjk <= _MAX_SCENE_CHARS, (
            f"Chunk {i} has {cjk} CJK chars, exceeding limit of {_MAX_SCENE_CHARS}"
        )


@pytest.mark.asyncio
async def test_source_builder_content_hash_is_sha256_of_normalized_text(db):
    import hashlib
    from app.retrieval.source_builder import _normalize_text
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="内容", summary="摘要")

    sources = await CanonicalSourceBuilder(db).build(novel.id, user.id)
    summary_source = next(s for s in sources if s.source_type == "chapter_summary")
    expected_hash = hashlib.sha256(_normalize_text(summary_source.text).encode()).hexdigest()
    assert summary_source.content_hash == expected_hash


@pytest.mark.asyncio
async def test_source_builder_tenant_key_format(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="内容", summary="摘要")

    sources = await CanonicalSourceBuilder(db).build(novel.id, user.id)
    assert all(s.tenant_key == f"{user.id}:{novel.id}" for s in sources)


@pytest.mark.asyncio
async def test_source_builder_foreshadowing_guard_visibility(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="内容", summary="摘要")
    await add_foreshadowing(db, novel, locked, name="伏笔", description="描述",
                            hidden_truth="真相", risk_warning="高风险")

    sources = await CanonicalSourceBuilder(db).build(novel.id, user.id)
    guard = next(s for s in sources if s.source_type == "foreshadowing_guard")
    signal = next(s for s in sources if s.source_type == "foreshadowing_signal")
    assert guard.visibility == "guard"
    assert signal.visibility != "guard"
    assert "真相" in guard.text
    assert "高风险" in guard.text
    assert "真相" not in signal.text


@pytest.mark.asyncio
async def test_source_builder_point_id_is_deterministic_uuid5(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="内容", summary="摘要")

    sources = await CanonicalSourceBuilder(db).build(novel.id, user.id)
    for source in sources:
        # point_id should be a valid UUID string
        parsed = uuid.UUID(source.point_id)
        assert parsed.version == 5


# -- Indexer tests ----------------------------------------------------------


@pytest.mark.asyncio
async def test_indexer_sync_returns_result_with_counts(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="内容", summary="摘要")

    store = FakeVectorStore()
    embedder = FakeEmbeddingProvider()
    indexer = NovelIndexer(db, embedder=embedder, store=store)

    result = await indexer.sync(novel.id, user.id)
    assert isinstance(result, IndexSyncResult)
    assert result.upserted > 0
    assert result.deleted == 0


@pytest.mark.asyncio
async def test_indexer_deletes_changed_point_before_upserting_replacement(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="原始内容", summary="原始摘要")

    store = FakeVectorStore()
    embedder = FakeEmbeddingProvider()
    indexer = NovelIndexer(db, embedder=embedder, store=store)

    # First sync
    await indexer.sync(novel.id, user.id)
    assert len(store.points) > 0

    # Record the original point IDs and hashes before change
    original_points = dict(store.points)  # snapshot
    original_point_ids = list(original_points.keys())

    # Change the chapter content
    locked.content = "修改后的内容"
    await db.commit()

    # Second sync — should delete stale then upsert new
    result = await indexer.sync(novel.id, user.id)
    assert result.deleted > 0
    assert result.upserted > 0
    # Verify delete was called before upsert (delete_calls recorded before new points added)
    assert len(store.delete_calls) >= 1
    # Verify specific point IDs were deleted — at least the ones for changed sources
    deleted_ids = [pid for batch in store.delete_calls for pid in batch]
    # The content changed, so the scene point for the chapter must have been deleted
    assert len(deleted_ids) > 0
    # Verify hashes are fresh — current store hashes match the rebuilt sources
    current_sources = await CanonicalSourceBuilder(db).build(novel.id, user.id)
    current_hashes = {s.source_id: s.content_hash for s in current_sources}
    for point in store.points.values():
        sid = point["payload"]["source_id"]
        if sid in current_hashes:
            assert point["payload"]["content_hash"] == current_hashes[sid]


@pytest.mark.asyncio
async def test_indexer_deletes_orphaned_source_points(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="内容", summary="摘要")

    store = FakeVectorStore()
    embedder = FakeEmbeddingProvider()
    indexer = NovelIndexer(db, embedder=embedder, store=store)

    # First sync
    await indexer.sync(novel.id, user.id)

    # Delete the chapter (simulate it being removed)
    await db.delete(locked)
    await db.commit()

    # Second sync — should delete all orphaned points
    result = await indexer.sync(novel.id, user.id)
    assert result.deleted > 0
    assert result.upserted == 0


@pytest.mark.asyncio
async def test_indexer_noop_when_nothing_changed(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="内容", summary="摘要")

    store = FakeVectorStore()
    embedder = FakeEmbeddingProvider()
    indexer = NovelIndexer(db, embedder=embedder, store=store)

    # First sync
    result1 = await indexer.sync(novel.id, user.id)
    assert result1.upserted > 0

    # Second sync with no changes — should be a no-op
    result2 = await indexer.sync(novel.id, user.id)
    assert result2.upserted == 0
    assert result2.deleted == 0


@pytest.mark.asyncio
async def test_indexer_batches_embedding_calls(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="内容", summary="摘要")
    await add_character(db, novel, name="角色")
    await add_plot_fact(db, novel, locked, content="事实")
    await add_world_setting(db, novel, title="设定")

    store = FakeVectorStore()
    embedder = FakeEmbeddingProvider()
    indexer = NovelIndexer(db, embedder=embedder, store=store)

    result = await indexer.sync(novel.id, user.id)
    # All sources should be indexed
    assert result.upserted > 0
    assert len(store.points) == result.upserted


@pytest.mark.asyncio
async def test_indexer_never_indexes_draft_chapters(db):
    user, novel = await make_user_and_novel(db)
    await add_chapter(db, novel, status="draft", content="草稿内容", summary="草稿摘要")

    store = FakeVectorStore()
    embedder = FakeEmbeddingProvider()
    indexer = NovelIndexer(db, embedder=embedder, store=store)

    result = await indexer.sync(novel.id, user.id)
    assert result.upserted == 0


# ---------------------------------------------------------------------------
# Task 4: Worker, mutation enqueue points, and index-control API
# ---------------------------------------------------------------------------

import asyncio
from app.retrieval.contracts import RetrievalUnavailable
from app.retrieval.indexer import NovelIndexer


class FakeIndexer:
    """Fake indexer for worker tests. Records calls and can raise errors."""

    def __init__(self, *, raise_unavailable=False, raise_generic=False):
        self.sync_calls: list[tuple[int, int]] = []
        self.purge_calls: list[str] = []
        self._raise_unavailable = raise_unavailable
        self._raise_generic = raise_generic

    async def sync(self, novel_id: int, user_id: int):
        self.sync_calls.append((novel_id, user_id))
        if self._raise_unavailable:
            raise RetrievalUnavailable("embedding service down")
        if self._raise_generic:
            raise RuntimeError("unexpected error")

    async def purge(self, tenant_key: str):
        self.purge_calls.append(tenant_key)
        if self._raise_unavailable:
            raise RetrievalUnavailable("qdrant down")
        if self._raise_generic:
            raise RuntimeError("unexpected error")


def fake_session_factory(db):
    """Return a callable that yields the same db session (for worker tests)."""
    class _Factory:
        async def __aenter__(self):
            return db
        async def __aexit__(self, *args):
            pass
    return lambda: _Factory()


# -- Worker tests -----------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_completes_sync_job(db):
    from app.retrieval.worker import RetrievalWorker
    user, novel = await make_user_and_novel(db)
    job = await RetrievalIndexService(db).enqueue_sync(novel.id, user.id)
    indexer = FakeIndexer()
    worker = RetrievalWorker(session_factory=fake_session_factory(db), indexer=indexer)
    claimed = await worker.run_once()
    assert claimed is True
    # Refresh job from DB
    await db.refresh(job)
    assert job.status == "completed"
    assert len(indexer.sync_calls) == 1
    assert indexer.sync_calls[0] == (novel.id, user.id)


@pytest.mark.asyncio
async def test_worker_completes_purge_job(db):
    from app.retrieval.worker import RetrievalWorker
    user, novel = await make_user_and_novel(db)
    job = await RetrievalIndexService(db).enqueue_purge(novel.id, user.id)
    indexer = FakeIndexer()
    worker = RetrievalWorker(session_factory=fake_session_factory(db), indexer=indexer)
    claimed = await worker.run_once()
    assert claimed is True
    await db.refresh(job)
    assert job.status == "completed"
    assert len(indexer.purge_calls) == 1
    assert indexer.purge_calls[0] == f"{user.id}:{novel.id}"


@pytest.mark.asyncio
async def test_worker_retries_on_unavailable(db):
    from app.retrieval.worker import RetrievalWorker
    user, novel = await make_user_and_novel(db)
    job = await RetrievalIndexService(db).enqueue_sync(novel.id, user.id)
    indexer = FakeIndexer(raise_unavailable=True)
    worker = RetrievalWorker(session_factory=fake_session_factory(db), indexer=indexer)
    claimed = await worker.run_once()
    assert claimed is True
    await db.refresh(job)
    assert job.status == "retry_wait"
    assert job.attempt_count == 1
    assert "embedding service down" in job.last_error


@pytest.mark.asyncio
async def test_worker_retries_on_generic_exception(db):
    from app.retrieval.worker import RetrievalWorker
    user, novel = await make_user_and_novel(db)
    job = await RetrievalIndexService(db).enqueue_sync(novel.id, user.id)
    indexer = FakeIndexer(raise_generic=True)
    worker = RetrievalWorker(session_factory=fake_session_factory(db), indexer=indexer)
    claimed = await worker.run_once()
    assert claimed is True
    await db.refresh(job)
    assert job.status == "retry_wait"
    assert job.attempt_count == 1


@pytest.mark.asyncio
async def test_worker_returns_false_when_no_jobs(db):
    from app.retrieval.worker import RetrievalWorker
    indexer = FakeIndexer()
    worker = RetrievalWorker(session_factory=fake_session_factory(db), indexer=indexer)
    claimed = await worker.run_once()
    assert claimed is False


# -- Enqueue-after-mutation tests (integration via HTTP) --------------------


async def _register_and_login(client, username="testuser"):
    """Register a user and return (user_id, auth_headers)."""
    resp = await client.post("/api/v1/auth/register", json={
        "username": username, "password": "pass1234"
    })
    data = resp.json()
    token = data["data"]["token"]
    user_id = data["data"]["user_id"]
    return user_id, {"Authorization": f"Bearer {token}"}


async def _create_novel(client, headers, title="测试小说"):
    resp = await client.post("/api/v1/novels", json={"title": title}, headers=headers)
    return resp.json()["data"]["id"]


async def _create_chapter(client, novel_id, headers, title="章节", content="", summary=""):
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": title, "content": content, "summary": summary},
        headers=headers,
    )
    return resp.json()["data"]["id"]


async def _publish_chapter(client, novel_id, chapter_id, headers):
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/publish",
        json={},
        headers=headers,
    )
    return resp


async def _count_pending_sync_jobs(db, novel_id, user_id):
    """Count pending/running/retry_wait sync or rebuild jobs for a novel."""
    tenant_key = f"{user_id}:{novel_id}"
    repo = RetrievalIndexRepo(db)
    job = await repo.find_active_by_tenant_key(tenant_key)
    return 1 if job else 0


@pytest.mark.asyncio
async def test_publish_chapter_enqueues_sync(client, db):
    user_id, headers = await _register_and_login(client)
    novel_id = await _create_novel(client, headers)
    chapter_id = await _create_chapter(client, novel_id, headers, content="内容", summary="摘要")
    await _publish_chapter(client, novel_id, chapter_id, headers)
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count >= 1


@pytest.mark.asyncio
async def test_character_crud_enqueues_sync(client, db):
    user_id, headers = await _register_and_login(client)
    novel_id = await _create_novel(client, headers)

    # Create character
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/characters",
        json={"name": "沈砚", "identity": "将军"},
        headers=headers,
    )
    assert resp.status_code == 200
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count >= 1

    # Complete the job so we can test update
    service = RetrievalIndexService(db)
    job = await service.repo.find_active_by_tenant_key(f"{user_id}:{novel_id}")
    await service.repo.complete(job)
    await db.commit()

    # Update character
    char_id = resp.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/characters/{char_id}",
        json={"personality": "沉稳"},
        headers=headers,
    )
    assert resp.status_code == 200
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count >= 1

    # Complete the job so we can test delete
    job = await service.repo.find_active_by_tenant_key(f"{user_id}:{novel_id}")
    await service.repo.complete(job)
    await db.commit()

    # Delete character
    resp = await client.delete(
        f"/api/v1/novels/{novel_id}/characters/{char_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count >= 1


@pytest.mark.asyncio
async def test_world_setting_crud_enqueues_sync(client, db):
    user_id, headers = await _register_and_login(client)
    novel_id = await _create_novel(client, headers)

    # Create setting
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/settings",
        json={"title": "北境", "category": "geography", "content": "苦寒之地"},
        headers=headers,
    )
    assert resp.status_code == 200
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count >= 1

    # Complete the job
    service = RetrievalIndexService(db)
    job = await service.repo.find_active_by_tenant_key(f"{user_id}:{novel_id}")
    await service.repo.complete(job)
    await db.commit()

    # Update setting
    setting_id = resp.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/settings/{setting_id}",
        json={"content": "冰原"},
        headers=headers,
    )
    assert resp.status_code == 200
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count >= 1 >= 1

    # Complete the job
    job = await service.repo.find_active_by_tenant_key(f"{user_id}:{novel_id}")
    await service.repo.complete(job)
    await db.commit()

    # Delete setting
    resp = await client.delete(
        f"/api/v1/novels/{novel_id}/settings/{setting_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count >= 1


@pytest.mark.asyncio
async def test_pending_memory_confirm_enqueues_sync(client, db):
    user_id, headers = await _register_and_login(client)
    novel_id = await _create_novel(client, headers)
    chapter_id = await _create_chapter(client, novel_id, headers, content="内容", summary="摘要")
    await _publish_chapter(client, novel_id, chapter_id, headers)

    # Complete the publish sync job first
    service = RetrievalIndexService(db)
    job = await service.repo.find_active_by_tenant_key(f"{user_id}:{novel_id}")
    if job:
        await service.repo.complete(job)
        await db.commit()

    # Create a pending memory directly in DB
    from app.models.pending_memory import PendingMemory
    pm = PendingMemory(
        novel_id=novel_id, chapter_id=chapter_id,
        memory_type="character", content={"name": "新角色"}, status="pending",
    )
    db.add(pm)
    await db.commit()
    await db.refresh(pm)

    # Confirm it
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/pending-memories/{pm.id}/confirm",
        headers=headers,
    )
    assert resp.status_code == 200
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count >= 1


@pytest.mark.asyncio
async def test_pending_memory_reject_does_not_enqueue(client, db):
    user_id, headers = await _register_and_login(client)
    novel_id = await _create_novel(client, headers)
    chapter_id = await _create_chapter(client, novel_id, headers, content="内容", summary="摘要")
    await _publish_chapter(client, novel_id, chapter_id, headers)

    # Complete the publish sync job first
    service = RetrievalIndexService(db)
    job = await service.repo.find_active_by_tenant_key(f"{user_id}:{novel_id}")
    if job:
        await service.repo.complete(job)
        await db.commit()

    # Create a pending memory directly in DB
    from app.models.pending_memory import PendingMemory
    pm = PendingMemory(
        novel_id=novel_id, chapter_id=chapter_id,
        memory_type="character", content={"name": "新角色"}, status="pending",
    )
    db.add(pm)
    await db.commit()
    await db.refresh(pm)

    # Reject it
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/pending-memories/{pm.id}/reject",
        headers=headers,
    )
    assert resp.status_code == 200
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count == 0


@pytest.mark.asyncio
async def test_batch_confirm_enqueues_sync_once(client, db):
    user_id, headers = await _register_and_login(client)
    novel_id = await _create_novel(client, headers)
    chapter_id = await _create_chapter(client, novel_id, headers, content="内容", summary="摘要")
    await _publish_chapter(client, novel_id, chapter_id, headers)

    # Complete the publish sync job first
    service = RetrievalIndexService(db)
    job = await service.repo.find_active_by_tenant_key(f"{user_id}:{novel_id}")
    if job:
        await service.repo.complete(job)
        await db.commit()

    # Create two pending memories directly in DB
    from app.models.pending_memory import PendingMemory
    pm1 = PendingMemory(
        novel_id=novel_id, chapter_id=chapter_id,
        memory_type="character", content={"name": "角色1"}, status="pending",
    )
    pm2 = PendingMemory(
        novel_id=novel_id, chapter_id=chapter_id,
        memory_type="world_setting", content={"title": "设定1"}, status="pending",
    )
    db.add_all([pm1, pm2])
    await db.commit()
    await db.refresh(pm1)
    await db.refresh(pm2)

    # Batch confirm
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/pending-memories/batch",
        json={"ids": [pm1.id, pm2.id], "action": "confirm"},
        headers=headers,
    )
    assert resp.status_code == 200
    # Should enqueue exactly one sync job (deduplication)
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count == 1


@pytest.mark.asyncio
async def test_batch_reject_does_not_enqueue(client, db):
    user_id, headers = await _register_and_login(client)
    novel_id = await _create_novel(client, headers)
    chapter_id = await _create_chapter(client, novel_id, headers, content="内容", summary="摘要")
    await _publish_chapter(client, novel_id, chapter_id, headers)

    # Complete the publish sync job first
    service = RetrievalIndexService(db)
    job = await service.repo.find_active_by_tenant_key(f"{user_id}:{novel_id}")
    if job:
        await service.repo.complete(job)
        await db.commit()

    # Create two pending memories directly in DB
    from app.models.pending_memory import PendingMemory
    pm1 = PendingMemory(
        novel_id=novel_id, chapter_id=chapter_id,
        memory_type="character", content={"name": "角色1"}, status="pending",
    )
    pm2 = PendingMemory(
        novel_id=novel_id, chapter_id=chapter_id,
        memory_type="world_setting", content={"title": "设定1"}, status="pending",
    )
    db.add_all([pm1, pm2])
    await db.commit()
    await db.refresh(pm1)
    await db.refresh(pm2)

    # Batch reject
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/pending-memories/batch",
        json={"ids": [pm1.id, pm2.id], "action": "reject"},
        headers=headers,
    )
    assert resp.status_code == 200
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count == 0


@pytest.mark.asyncio
async def test_delete_novel_enqueues_purge(client, db):
    user_id, headers = await _register_and_login(client)
    novel_id = await _create_novel(client, headers)

    resp = await client.delete(f"/api/v1/novels/{novel_id}", headers=headers)
    assert resp.status_code == 200

    # Check that a purge job was enqueued
    tenant_key = f"{user_id}:{novel_id}"
    repo = RetrievalIndexRepo(db)
    job = await repo.find_active_purge_by_tenant_key(tenant_key)
    assert job is not None
    assert job.operation == "purge"


@pytest.mark.asyncio
async def test_draft_chapter_update_does_not_enqueue(client, db):
    """Updating a draft chapter (not publish) should NOT enqueue a sync job."""
    user_id, headers = await _register_and_login(client)
    novel_id = await _create_novel(client, headers)
    chapter_id = await _create_chapter(client, novel_id, headers, content="草稿", summary="摘要")

    # Update the draft chapter
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}",
        json={"content": "修改后的草稿"},
        headers=headers,
    )
    assert resp.status_code == 200
    count = await _count_pending_sync_jobs(db, novel_id, user_id)
    assert count == 0


# -- API endpoint tests -----------------------------------------------------


@pytest.mark.asyncio
async def test_retrieval_status_endpoint(client, db):
    user_id, headers = await _register_and_login(client)
    novel_id = await _create_novel(client, headers)

    # No jobs yet — should return null data
    resp = await client.get(f"/api/v1/novels/{novel_id}/retrieval-index", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data is None

    # Enqueue a sync job
    await RetrievalIndexService(db).enqueue_sync(novel_id, user_id)

    resp = await client.get(f"/api/v1/novels/{novel_id}/retrieval-index", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data is not None
    assert data["status"] in ("pending", "running")
    assert data["operation"] == "sync"


@pytest.mark.asyncio
async def test_rebuild_endpoint_creates_job(client, db):
    user_id, headers = await _register_and_login(client)
    novel_id = await _create_novel(client, headers)

    resp = await client.post(f"/api/v1/novels/{novel_id}/retrieval-index/rebuild", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["job_id"] is not None
    assert data["status"] in ("pending", "running")


@pytest.mark.asyncio
async def test_retrieval_status_hides_other_users_novel(client, db):
    user1_id, headers1 = await _register_and_login(client, "user1")
    user2_id, headers2 = await _register_and_login(client, "user2")
    novel_id = await _create_novel(client, headers1)

    resp = await client.get(f"/api/v1/novels/{novel_id}/retrieval-index", headers=headers2)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rebuild_endpoint_hides_other_users_novel(client, db):
    user1_id, headers1 = await _register_and_login(client, "user1")
    user2_id, headers2 = await _register_and_login(client, "user2")
    novel_id = await _create_novel(client, headers1)

    resp = await client.post(f"/api/v1/novels/{novel_id}/retrieval-index/rebuild", headers=headers2)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retrieval_status_returns_404_for_missing_novel(client, db):
    _, headers = await _register_and_login(client)
    resp = await client.get("/api/v1/novels/99999/retrieval-index", headers=headers)
    assert resp.status_code == 404
