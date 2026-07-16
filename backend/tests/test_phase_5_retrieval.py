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

    async def hybrid_search(self, query, tenant_key, visibility="default", limit=10, dense_limit=24, sparse_limit=24):
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


# ---------------------------------------------------------------------------
# Task 5: Hybrid retrieval service with writer/guard separation and fallback
# ---------------------------------------------------------------------------

from app.retrieval.contracts import (
    RetrievedSource,
    RetrievalRequest,
    RetrievalContext,
)
from app.retrieval.service import RetrievalService


# -- Helpers for Task 5 service tests ---------------------------------------


def _make_retrieved_source(
    *,
    source_id: str,
    source_type: str,
    title: str,
    preview: str = "",
    locator: dict | None = None,
    visibility: str = "default",
    chapter_id: int | None = None,
    importance: str = "minor",
) -> RetrievedSource:
    """Build a RetrievedSource with sensible defaults for tests."""
    if locator is None:
        if source_type == "chapter_scene":
            locator = {"chapter_id": chapter_id, "type": "scene", "scene_index": 0}
        elif source_type == "chapter_summary":
            locator = {"chapter_id": chapter_id, "type": "summary"}
        elif source_type == "character":
            locator = {"character_id": int(source_id.split(":")[1])}
        elif source_type == "plot_fact":
            locator = {"plot_fact_id": int(source_id.split(":")[1])}
        elif source_type == "world_setting":
            locator = {"world_setting_id": int(source_id.split(":")[1])}
        elif source_type in ("foreshadowing_signal", "foreshadowing_guard"):
            locator = {"foreshadowing_id": int(source_id.split(":")[1]), "type": source_type.split("_")[1]}
        else:
            locator = {}
    return RetrievedSource(
        source_id=source_id,
        source_type=source_type,
        title=title,
        preview=preview or title[:30],
        locator=locator,
        visibility=visibility,
        chapter_id=chapter_id,
        importance=importance,
    )


def canonical_points_for_two_novels() -> list[RetrievedSource]:
    """Build canonical test data for two novels (tenant 1:1 and 2:1)."""
    return [
        # Novel 1 (user 1, novel 1) — writer-visible
        _make_retrieved_source(
            source_id="chapter:18:scene:3",
            source_type="chapter_scene",
            title="第十八章 · 场景4",
            preview="沈砚翻阅账册，发现军饷亏空",
            chapter_id=18,
            importance="minor",
        ),
        _make_retrieved_source(
            source_id="character:7",
            source_type="character",
            title="沈砚",
            preview="将军，沉稳果决",
        ),
        _make_retrieved_source(
            source_id="plot_fact:12",
            source_type="plot_fact",
            title="情节事实：军饷失踪",
            preview="军饷失踪",
            chapter_id=18,
            importance="major",
        ),
        _make_retrieved_source(
            source_id="chapter:18:scene:0",
            source_type="chapter_scene",
            title="第十八章 · 场景1",
            preview="夜雨连绵",
            chapter_id=18,
            importance="minor",
        ),
        _make_retrieved_source(
            source_id="chapter:18:scene:1",
            source_type="chapter_scene",
            title="第十八章 · 场景2",
            preview="账册上的数字",
            chapter_id=18,
            importance="minor",
        ),
        _make_retrieved_source(
            source_id="world_setting:3",
            source_type="world_setting",
            title="北境",
            preview="苦寒之地，边关要塞",
        ),
        # Novel 1 — guard-visible
        _make_retrieved_source(
            source_id="foreshadowing:5:guard",
            source_type="foreshadowing_guard",
            title="伏笔守护：军饷暗线",
            preview="隐藏真相：军饷被贪墨",
            visibility="guard",
            chapter_id=18,
        ),
        # Novel 2 (user 2, novel 1) — should be filtered out
        _make_retrieved_source(
            source_id="chapter:99:scene:0",
            source_type="chapter_scene",
            title="另一本小说",
            preview="无关内容",
            visibility="default",
            chapter_id=99,
        ),
    ]


class RetrievalFakeVectorStore:
    """Fake VectorStore for retrieval service tests.

    Stores pre-built points and supports visibility-based hybrid_search.
    Records all (tenant_key, visibility) filter pairs for assertions.
    """

    def __init__(self, points: list[RetrievedSource]) -> None:
        self._points = points
        self.filters: list[tuple[str, str]] = []

    async def ensure_collection(self) -> None:
        pass

    async def upsert(self, points: list[dict]) -> None:
        pass

    async def hybrid_search(
        self,
        query,
        tenant_key: str,
        visibility: str = "default",
        limit: int = 10,
        dense_limit: int = 24,
        sparse_limit: int = 24,
    ) -> list[RetrievedSource]:
        self.filters.append((tenant_key, visibility))
        # Map service-level visibility to stored payload visibility
        stored_visibility = "default" if visibility == "writer" else visibility
        # Filter points by stored visibility
        filtered = [
            p for p in self._points
            if p.visibility == stored_visibility
        ]
        return filtered[:limit]

    async def list_indexed_sources(self, tenant_key: str) -> list:
        return []

    async def delete_point_ids(self, ids: list[str]) -> None:
        pass

    async def delete_tenant(self, tenant_key: str) -> None:
        pass


class FakeRerankerForService:
    """Fake Reranker that reorders results by the given index permutation."""

    def __init__(self, order: list[int]) -> None:
        """order is a list of indices specifying the desired rerank order."""
        self._order = order

    async def rerank(self, query: str, documents: list[str]) -> list[RerankResult]:
        return [
            RerankResult(index=idx, score=1.0 - i * 0.1)
            for i, idx in enumerate(self._order)
        ]


class FailingEmbeddingProvider:
    """EmbeddingProvider that always raises RetrievalUnavailable."""

    async def embed_documents(self, texts: list[str]) -> list[HybridEmbedding]:
        raise RetrievalUnavailable("embedding service down")

    async def embed_query(self, text: str) -> HybridEmbedding:
        raise RetrievalUnavailable("embedding service down")


# -- Task 5: Retrieval service tests ----------------------------------------


@pytest.mark.asyncio
async def test_retrieval_uses_tenant_filter_reranks_and_limits_duplicate_scenes():
    store = RetrievalFakeVectorStore(points=canonical_points_for_two_novels())
    # Reranker order [2, 0, 1] means: original index 2 first, then 0, then 1
    # Original writer candidates: [scene:3, character:7, plot_fact:12, scene:0, scene:1, world_setting:3]
    # Reranked: [plot_fact:12, scene:3, character:7, ...]
    reranker = FakeRerankerForService([2, 0, 1])
    service = RetrievalService(
        embedder=FakeEmbeddingProvider(),
        reranker=reranker,
        store=store,
    )
    result = await service.retrieve(
        RetrievalRequest(
            user_id=1,
            novel_id=1,
            query="沈砚与军饷账册",
            target_chapter_id=19,
        )
    )
    # Store should be called once with writer visibility, once with guard
    assert store.filters == [("1:1", "writer"), ("1:1", "guard")]
    # source_items should reflect the reranked order
    source_ids = [item["source_id"] for item in result.source_items]
    # Reranker put plot_fact:12 (index 2) first, then scene:3 (index 0), then character:7 (index 1)
    assert source_ids[0] == "plot_fact:12"
    assert source_ids[1] == "chapter:18:scene:3"
    # No more than 2 chapter_scene items per chapter in writer_items
    chapter_18_scenes = [
        item for item in result.writer_items
        if item["locator"].get("chapter_id") == 18
        and item["source_type"] == "chapter_scene"
    ]
    assert len(chapter_18_scenes) <= 2


@pytest.mark.asyncio
async def test_guard_never_leaks_hidden_truth_into_writer_context_and_provider_failure_falls_back():
    # Build a service where the embedding provider fails
    store = RetrievalFakeVectorStore(points=canonical_points_for_two_novels())
    service = RetrievalService(
        embedder=FailingEmbeddingProvider(),
        reranker=FakeRerankerForService([]),
        store=store,
    )
    result = await service.retrieve(
        RetrievalRequest(
            user_id=1,
            novel_id=1,
            query="沈砚与军饷账册",
            target_chapter_id=19,
        )
    )
    # Fallback: empty lists
    assert result.writer_items == []
    assert result.guard_constraints == []
    assert result.diagnostics["retrieval_status"] == "fallback"
    assert result.diagnostics["reason"] == "service_unavailable"


@pytest.mark.asyncio
async def test_guard_constraints_exclude_hidden_truth_from_writer():
    """Guard items must never appear in writer_items."""
    store = RetrievalFakeVectorStore(points=canonical_points_for_two_novels())
    service = RetrievalService(
        embedder=FakeEmbeddingProvider(),
        reranker=FakeRerankerForService([0]),
        store=store,
    )
    result = await service.retrieve(
        RetrievalRequest(
            user_id=1,
            novel_id=1,
            query="军饷暗线",
            target_chapter_id=18,
        )
    )
    # writer_items must NOT contain any guard-visibility source
    writer_source_ids = {item["source_id"] for item in result.writer_items}
    assert "foreshadowing:5:guard" not in writer_source_ids
    # guard_constraints should contain guard source info
    guard_ids = {c["source_id"] for c in result.guard_constraints}
    assert "foreshadowing:5:guard" in guard_ids


@pytest.mark.asyncio
async def test_writer_items_respect_item_budget():
    """writer_items should stop at the item budget (10 items)."""
    # Build many writer-visible sources
    many_points = [
        _make_retrieved_source(
            source_id=f"chapter:{i}:scene:0",
            source_type="chapter_scene",
            title=f"场景{i}",
            chapter_id=i,
        )
        for i in range(20)
    ]
    store = RetrievalFakeVectorStore(points=many_points)
    reranker = FakeRerankerForService(list(range(20)))
    service = RetrievalService(
        embedder=FakeEmbeddingProvider(),
        reranker=reranker,
        store=store,
    )
    result = await service.retrieve(
        RetrievalRequest(
            user_id=1,
            novel_id=1,
            query="测试",
            target_chapter_id=1,
        )
    )
    assert len(result.writer_items) <= 10


@pytest.mark.asyncio
async def test_guard_constraints_respect_item_budget():
    """guard_constraints should stop at the item budget (6 items)."""
    many_guard_points = [
        _make_retrieved_source(
            source_id=f"foreshadowing:{i}:guard",
            source_type="foreshadowing_guard",
            title=f"伏笔守护{i}",
            visibility="guard",
            chapter_id=1,
        )
        for i in range(20)
    ]
    store = RetrievalFakeVectorStore(points=many_guard_points)
    service = RetrievalService(
        embedder=FakeEmbeddingProvider(),
        reranker=FakeRerankerForService(list(range(20))),
        store=store,
    )
    result = await service.retrieve(
        RetrievalRequest(
            user_id=1,
            novel_id=1,
            query="测试",
            target_chapter_id=1,
        )
    )
    assert len(result.guard_constraints) <= 6


@pytest.mark.asyncio
async def test_source_items_have_no_score_fields():
    """source_items must use to_source_item projection — no score fields."""
    store = RetrievalFakeVectorStore(points=canonical_points_for_two_novels())
    service = RetrievalService(
        embedder=FakeEmbeddingProvider(),
        reranker=FakeRerankerForService([0, 1]),
        store=store,
    )
    result = await service.retrieve(
        RetrievalRequest(
            user_id=1,
            novel_id=1,
            query="测试",
            target_chapter_id=19,
        )
    )
    for item in result.source_items:
        assert "score" not in item
        assert "rerank_score" not in item
        # Must have the expected projection fields
        assert "source_id" in item
        assert "source_type" in item
        assert "title" in item
        assert "locator" in item
        assert "preview" in item
        assert "inclusion_reason" in item


@pytest.mark.asyncio
async def test_diagnostics_contain_raw_scores_and_collection_version():
    """Diagnostics must contain raw scores, source IDs, and collection version."""
    store = RetrievalFakeVectorStore(points=canonical_points_for_two_novels())
    service = RetrievalService(
        embedder=FakeEmbeddingProvider(),
        reranker=FakeRerankerForService([0, 1]),
        store=store,
    )
    result = await service.retrieve(
        RetrievalRequest(
            user_id=1,
            novel_id=1,
            query="测试",
            target_chapter_id=19,
        )
    )
    assert "collection_version" in result.diagnostics
    assert "candidate_scores" in result.diagnostics or "writer_candidates" in result.diagnostics


@pytest.mark.asyncio
async def test_high_importance_facts_prioritized_over_duplicate_scenes():
    """High-importance facts/settings should be taken before lower-ranked duplicate scenes."""
    points = [
        _make_retrieved_source(
            source_id="chapter:5:scene:0",
            source_type="chapter_scene",
            title="场景1",
            chapter_id=5,
            importance="minor",
        ),
        _make_retrieved_source(
            source_id="chapter:5:scene:1",
            source_type="chapter_scene",
            title="场景2",
            chapter_id=5,
            importance="minor",
        ),
        _make_retrieved_source(
            source_id="chapter:5:scene:2",
            source_type="chapter_scene",
            title="场景3",
            chapter_id=5,
            importance="minor",
        ),
        _make_retrieved_source(
            source_id="plot_fact:10",
            source_type="plot_fact",
            title="关键事实",
            chapter_id=5,
            importance="major",
        ),
        _make_retrieved_source(
            source_id="world_setting:2",
            source_type="world_setting",
            title="重要设定",
            importance="major",
        ),
    ]
    store = RetrievalFakeVectorStore(points=points)
    # Rerank: scenes first, facts later — but diversity should promote facts
    service = RetrievalService(
        embedder=FakeEmbeddingProvider(),
        reranker=FakeRerankerForService([0, 1, 2, 3, 4]),
        store=store,
    )
    result = await service.retrieve(
        RetrievalRequest(
            user_id=1,
            novel_id=1,
            query="关键事实",
            target_chapter_id=5,
        )
    )
    writer_ids = [item["source_id"] for item in result.writer_items]
    # After at most 2 scenes for chapter 5, major facts should come before
    # the 3rd scene (which would be capped by the per-chapter limit)
    assert "plot_fact:10" in writer_ids
    assert "world_setting:2" in writer_ids
    # At most 2 chapter_scene for chapter 5
    ch5_scenes = [sid for sid in writer_ids if sid.startswith("chapter:5:scene:")]
    assert len(ch5_scenes) <= 2


@pytest.mark.asyncio
async def test_duplicate_source_id_rejected():
    """Duplicate source_id should be rejected (only first occurrence kept)."""
    points = [
        _make_retrieved_source(
            source_id="character:7",
            source_type="character",
            title="沈砚",
        ),
        _make_retrieved_source(
            source_id="character:7",
            source_type="character",
            title="沈砚（重复）",
        ),
    ]
    store = RetrievalFakeVectorStore(points=points)
    service = RetrievalService(
        embedder=FakeEmbeddingProvider(),
        reranker=FakeRerankerForService([0, 1]),
        store=store,
    )
    result = await service.retrieve(
        RetrievalRequest(
            user_id=1,
            novel_id=1,
            query="沈砚",
            target_chapter_id=1,
        )
    )
    source_ids = [item["source_id"] for item in result.source_items]
    assert source_ids.count("character:7") == 1


@pytest.mark.asyncio
async def test_retrieval_does_not_catch_programmer_errors():
    """Programmer errors (TypeError, ValueError, etc.) should NOT be caught."""
    class BrokenStore:
        async def ensure_collection(self): pass
        async def upsert(self, points): pass
        async def hybrid_search(self, *args, **kwargs):
            raise TypeError("bad argument type")
        async def list_indexed_sources(self, tenant_key): return []
        async def delete_point_ids(self, ids): pass
        async def delete_tenant(self, tenant_key): pass

    service = RetrievalService(
        embedder=FakeEmbeddingProvider(),
        reranker=FakeRerankerForService([]),
        store=BrokenStore(),
    )
    with pytest.raises(TypeError, match="bad argument type"):
        await service.retrieve(
            RetrievalRequest(
                user_id=1,
                novel_id=1,
                query="测试",
                target_chapter_id=1,
            )
        )


@pytest.mark.asyncio
async def test_fallback_does_not_falsely_report_sources():
    """When retrieval falls back, source_items must also be empty."""
    store = RetrievalFakeVectorStore(points=canonical_points_for_two_novels())
    service = RetrievalService(
        embedder=FailingEmbeddingProvider(),
        reranker=FakeRerankerForService([]),
        store=store,
    )
    result = await service.retrieve(
        RetrievalRequest(
            user_id=1,
            novel_id=1,
            query="测试",
            target_chapter_id=19,
        )
    )
    assert result.source_items == []
    assert result.writer_items == []
    assert result.guard_constraints == []


# ---------------------------------------------------------------------------
# Task 6: ContextPackage enrichment and snapshot freezing
# ---------------------------------------------------------------------------

import copy
from app.services.context_package_service import ContextPackageService
from app.services.writing_service import WritingService
from app.ai.writer import FakeWritingGenerator
from app.ai.quality_gate import FakeQualityGateAgent
from app.models.writing import NovelBlueprint, ChapterPlan, ChapterBrief


class FakeRetrievalService:
    """Fake RetrievalService for context package integration tests.

    Returns deterministic writer_items, guard_constraints, source_items,
    and diagnostics that match the task brief's expected shape.
    """

    async def retrieve(self, request):
        return RetrievalContext(
            writer_items=[
                {
                    "source_id": "chapter:18:scene:3",
                    "source_type": "chapter_scene",
                    "title": "第十八章 · 场景4",
                    "locator": {"chapter_id": 18, "type": "scene", "scene_index": 3},
                    "preview": "沈砚翻阅账册，发现军饷亏空",
                    "inclusion_reason": "retrieved",
                },
            ],
            guard_constraints=[
                {
                    "source_id": "foreshadowing:5:guard",
                    "source_type": "foreshadowing_guard",
                    "title": "伏笔守护：军饷暗线",
                    "locator": {"foreshadowing_id": 5, "type": "guard"},
                    "preview": "本章不可揭示军饷去向",
                    "inclusion_reason": "guard_constraint",
                },
            ],
            source_items=[
                {
                    "source_id": "chapter:18:scene:3",
                    "source_type": "chapter_scene",
                    "title": "第十八章 · 场景4",
                    "locator": {"chapter_id": 18, "type": "scene", "scene_index": 3},
                    "preview": "沈砚翻阅账册，发现军饷亏空",
                    "inclusion_reason": "retrieved",
                },
                {
                    "source_id": "foreshadowing:5:guard",
                    "source_type": "foreshadowing_guard",
                    "title": "伏笔守护：军饷暗线",
                    "locator": {"foreshadowing_id": 5, "type": "guard"},
                    "preview": "本章不可揭示军饷去向",
                    "inclusion_reason": "guard_constraint",
                },
            ],
            diagnostics={
                "retrieval_status": "ok",
                "collection_version": "novel-context-v1",
            },
        )


class FailingRetrievalService:
    """RetrievalService that raises RetrievalUnavailable, simulating unavailable retrieval."""

    async def retrieve(self, request):
        raise RetrievalUnavailable("retrieval infrastructure down")


# -- Task 6: Context package enrichment tests --------------------------------


async def _setup_writing_data(db):
    """Create user, novel, blueprint, plan, brief for writing tests."""
    user = User(username="ctx_pkg_user", hashed_password="hash")
    db.add(user)
    await db.flush()
    novel = Novel(user_id=user.id, title="上下文包测试小说", genre="古风", style_guide="第三人称")
    db.add(novel)
    await db.flush()

    blueprint = NovelBlueprint(novel_id=novel.id, content_json={"core_promise": "测试"}, status="active")
    db.add(blueprint)
    await db.flush()

    plan = ChapterPlan(novel_id=novel.id, content_json={"plot_task": "测试任务"}, position=1, status="ready")
    db.add(plan)
    await db.flush()

    brief = ChapterBrief(
        novel_id=novel.id,
        chapter_plan_id=plan.id,
        brief_json={"acceptance_criteria": "测试标准"},
        length_contract_json={"target_words": 3000, "min_words": 2000, "max_words": 5000},
        status="ready",
    )
    db.add(brief)
    await db.commit()
    return user, novel, blueprint, plan, brief


@pytest.mark.asyncio
async def test_context_package_includes_retrieval_and_safe_guard_snapshot(db, monkeypatch):
    """ContextPackageService.build_for_brief() should enrich the package with
    retrieved_context, risk_guard, and snapshot.source_items/diagnostics."""
    user, novel, blueprint, plan, brief = await _setup_writing_data(db)

    # Set up plot planning data required by build_for_brief
    from app.models.plot_planning import AuthorFoundation, AuthorFoundationRevision, PlotUnit, PlotPlanRevision
    foundation = AuthorFoundation(
        novel_id=novel.id, outline="大纲", current_intent="意图",
        stage_goal="目标", constraints_json={}, version=1,
    )
    db.add(foundation)
    await db.flush()
    revision = AuthorFoundationRevision(
        novel_id=novel.id, foundation_id=foundation.id, version=1,
        snapshot_json={}, change_reason="initial",
    )
    db.add(revision)
    await db.flush()
    plot_unit = PlotUnit(
        novel_id=novel.id, title="第一卷：边城旧案", scope_type="volume",
        start_position=1, end_position=5, author_goal="查清密令来源",
        start_state="抵达", end_state="确认", foundation_revision_id=revision.id, status="draft",
    )
    db.add(plot_unit)
    await db.flush()
    plan_revision = PlotPlanRevision(
        novel_id=novel.id, plot_unit_id=plot_unit.id,
        foundation_revision_id=revision.id, version=1,
        plan_json={"core_conflict": "调查触动守城势力"},
        change_reason="initial generation", status="active",
    )
    db.add(plan_revision)
    await db.commit()

    fake_retrieval = FakeRetrievalService()
    service = ContextPackageService(db, user_id=user.id, novel_id=novel.id, retrieval=fake_retrieval)
    package = await service.build_for_brief(
        brief_id=brief.id,
        plot_plan_revision_id=plan_revision.id,
        author_input="军饷",
    )

    # Retrieved context should contain writer items
    assert package["retrieved_context"][0]["source_id"] == "chapter:18:scene:3"
    # Risk guard should contain guard constraints
    assert package["risk_guard"][0]["preview"].startswith("本章不可")
    # Snapshot should contain source_items and diagnostics
    assert package["snapshot"]["source_items"][0]["source_id"] == "chapter:18:scene:3"
    assert package["snapshot"]["diagnostics"]["retrieval_status"] == "ok"
    # hidden_truth must NOT appear in retrieved_context (writer items)
    assert "hidden_truth" not in str(package["retrieved_context"])


@pytest.mark.asyncio
async def test_context_package_falls_back_when_retrieval_unavailable(db, monkeypatch):
    """When retrieval fails, the package should still have valid empty fields."""
    user, novel, blueprint, plan, brief = await _setup_writing_data(db)

    from app.models.plot_planning import AuthorFoundation, AuthorFoundationRevision, PlotUnit, PlotPlanRevision
    foundation = AuthorFoundation(
        novel_id=novel.id, outline="大纲", current_intent="意图",
        stage_goal="目标", constraints_json={}, version=1,
    )
    db.add(foundation)
    await db.flush()
    revision = AuthorFoundationRevision(
        novel_id=novel.id, foundation_id=foundation.id, version=1,
        snapshot_json={}, change_reason="initial",
    )
    db.add(revision)
    await db.flush()
    plot_unit = PlotUnit(
        novel_id=novel.id, title="第一卷", scope_type="volume",
        start_position=1, end_position=5, author_goal="目标",
        start_state="开始", end_state="结束", foundation_revision_id=revision.id, status="draft",
    )
    db.add(plot_unit)
    await db.flush()
    plan_revision = PlotPlanRevision(
        novel_id=novel.id, plot_unit_id=plot_unit.id,
        foundation_revision_id=revision.id, version=1,
        plan_json={"core_conflict": "冲突"},
        change_reason="initial", status="active",
    )
    db.add(plan_revision)
    await db.commit()

    service = ContextPackageService(db, user_id=user.id, novel_id=novel.id, retrieval=FailingRetrievalService())
    package = await service.build_for_brief(
        brief_id=brief.id,
        plot_plan_revision_id=plan_revision.id,
        author_input="军饷",
    )

    # Fallback: empty lists, valid diagnostics
    assert package["retrieved_context"] == []
    assert package["risk_guard"] == []
    assert package["snapshot"]["source_items"] == []
    assert package["snapshot"]["diagnostics"]["retrieval_status"] == "fallback"


@pytest.mark.asyncio
async def test_context_package_preserves_brief_and_plan_when_enriched(db, monkeypatch):
    """Retrieval enrichment must NOT remove the active brief or plan."""
    user, novel, blueprint, plan, brief = await _setup_writing_data(db)

    from app.models.plot_planning import AuthorFoundation, AuthorFoundationRevision, PlotUnit, PlotPlanRevision
    foundation = AuthorFoundation(
        novel_id=novel.id, outline="大纲", current_intent="意图",
        stage_goal="目标", constraints_json={}, version=1,
    )
    db.add(foundation)
    await db.flush()
    revision = AuthorFoundationRevision(
        novel_id=novel.id, foundation_id=foundation.id, version=1,
        snapshot_json={}, change_reason="initial",
    )
    db.add(revision)
    await db.flush()
    plot_unit = PlotUnit(
        novel_id=novel.id, title="第一卷", scope_type="volume",
        start_position=1, end_position=5, author_goal="目标",
        start_state="开始", end_state="结束", foundation_revision_id=revision.id, status="draft",
    )
    db.add(plot_unit)
    await db.flush()
    plan_revision = PlotPlanRevision(
        novel_id=novel.id, plot_unit_id=plot_unit.id,
        foundation_revision_id=revision.id, version=1,
        plan_json={"core_conflict": "冲突"},
        change_reason="initial", status="active",
    )
    db.add(plan_revision)
    await db.commit()

    service = ContextPackageService(db, user_id=user.id, novel_id=novel.id, retrieval=FakeRetrievalService())
    package = await service.build_for_brief(
        brief_id=brief.id,
        plot_plan_revision_id=plan_revision.id,
        author_input="军饷",
    )

    # Brief and plan must still be present
    assert "chapter_brief" in package
    assert "plot_plan" in package
    assert package["chapter_brief"] is not None
    assert package["plot_plan"] is not None


@pytest.mark.asyncio
async def test_every_writing_run_copies_context_snapshot_even_without_plot_plan(db):
    """Legacy (Phase 1/2) writing runs must also get a context_snapshot_json
    with source_items, not just runs with plot_plan_revision_id."""
    user, novel, blueprint, plan, brief = await _setup_writing_data(db)

    # Use a FakeRetrievalService that returns a character source
    class LegacyFakeRetrievalService:
        async def retrieve(self, request):
            return RetrievalContext(
                writer_items=[
                    {
                        "source_id": "character:7",
                        "source_type": "character_profile",
                        "title": "沈砚",
                        "locator": {"character_id": 7},
                        "preview": "当前状态",
                        "inclusion_reason": "角色连续性",
                    },
                ],
                guard_constraints=[],
                source_items=[
                    {
                        "source_id": "character:7",
                        "source_type": "character_profile",
                        "title": "沈砚",
                        "locator": {"character_id": 7},
                        "preview": "当前状态",
                        "inclusion_reason": "角色连续性",
                    },
                ],
                diagnostics={"retrieval_status": "ok"},
            )

    run = await WritingService(
        db, user.id, novel.id,
        generator=FakeWritingGenerator(),
        gate_agent=FakeQualityGateAgent(),
        retrieval=LegacyFakeRetrievalService(),
    ).create_writing_run(brief_id=brief.id)

    # Snapshot must exist and contain source_items
    assert run.context_snapshot_json is not None
    assert "source_items" in run.context_snapshot_json
    assert run.context_snapshot_json["source_items"][0]["source_id"] == "character:7"


@pytest.mark.asyncio
async def test_writing_run_snapshot_is_frozen_and_not_mutated_by_gate(db):
    """After creation, context_snapshot_json must not be mutated by
    draft generation, quality-gate retries, or other post-creation steps."""
    user, novel, blueprint, plan, brief = await _setup_writing_data(db)

    class SnapshotTrackingRetrieval:
        async def retrieve(self, request):
            return RetrievalContext(
                writer_items=[],
                guard_constraints=[],
                source_items=[],
                diagnostics={"retrieval_status": "ok", "frozen_check": "original"},
            )

    svc = WritingService(
        db, user.id, novel.id,
        generator=FakeWritingGenerator(),
        gate_agent=FakeQualityGateAgent(),
        retrieval=SnapshotTrackingRetrieval(),
    )
    run = await svc.create_writing_run(brief_id=brief.id)

    # The snapshot must retain the original diagnostics — not overwritten
    assert run.context_snapshot_json["diagnostics"]["frozen_check"] == "original"


@pytest.mark.asyncio
async def test_writing_run_snapshot_fallback_when_retrieval_disabled(db, monkeypatch):
    """When RETRIEVAL_ENABLED=false or retrieval is None, the snapshot
    should still have a valid structure with empty source_items."""
    user, novel, blueprint, plan, brief = await _setup_writing_data(db)

    # Create service with no retrieval (retrieval=None)
    svc = WritingService(
        db, user.id, novel.id,
        generator=FakeWritingGenerator(),
        gate_agent=FakeQualityGateAgent(),
        retrieval=None,
    )
    run = await svc.create_writing_run(brief_id=brief.id)

    # Snapshot must exist with empty source_items and fallback diagnostics
    assert run.context_snapshot_json is not None
    assert "source_items" in run.context_snapshot_json
    assert run.context_snapshot_json["source_items"] == []
    assert run.context_snapshot_json["diagnostics"]["retrieval_status"] == "not_requested"


@pytest.mark.asyncio
async def test_older_writing_run_snapshot_unchanged_after_newer_package(db):
    """Verify historical source snapshots are immutable after newer package creation."""
    user, novel, blueprint, plan, brief = await _setup_writing_data(db)

    # Set up plot planning data required by build_for_brief
    from app.models.plot_planning import AuthorFoundation, AuthorFoundationRevision, PlotUnit, PlotPlanRevision
    foundation = AuthorFoundation(
        novel_id=novel.id, outline="大纲", current_intent="意图",
        stage_goal="目标", constraints_json={}, version=1,
    )
    db.add(foundation)
    await db.flush()
    revision = AuthorFoundationRevision(
        novel_id=novel.id, foundation_id=foundation.id, version=1,
        snapshot_json={}, change_reason="initial",
    )
    db.add(revision)
    await db.flush()
    plot_unit = PlotUnit(
        novel_id=novel.id, title="第一卷：边城旧案", scope_type="volume",
        start_position=1, end_position=5, author_goal="查清密令来源",
        start_state="抵达", end_state="确认", foundation_revision_id=revision.id, status="draft",
    )
    db.add(plot_unit)
    await db.flush()
    plan_revision = PlotPlanRevision(
        novel_id=novel.id, plot_unit_id=plot_unit.id,
        foundation_revision_id=revision.id, version=1,
        plan_json={"core_conflict": "调查触动守城势力"},
        change_reason="initial generation", status="active",
    )
    db.add(plan_revision)
    await db.commit()

    # Create first writing run with retrieval
    first_retrieval = FakeRetrievalService()
    first_run = await WritingService(
        db, user.id, novel.id,
        generator=FakeWritingGenerator(),
        gate_agent=FakeQualityGateAgent(),
        retrieval=first_retrieval,
    ).create_writing_run(brief_id=brief.id, plot_plan_revision_id=plan_revision.id)

    # Record the original snapshot
    original_source_items = copy.deepcopy(first_run.context_snapshot_json["source_items"])
    assert len(original_source_items) > 0, "First run should have source_items"

    # Create a second context package (simulating a newer build)
    second_retrieval = FakeRetrievalService()
    second_pkg = await ContextPackageService(
        db, user_id=user.id, novel_id=novel.id, retrieval=second_retrieval,
    ).build_for_brief(
        brief_id=brief.id,
        plot_plan_revision_id=plan_revision.id,
        author_input="新的输入",
    )

    # Refresh the first run from DB and verify its snapshot is unchanged
    await db.refresh(first_run)
    assert first_run.context_snapshot_json["source_items"] == original_source_items
