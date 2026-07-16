# Phase 5 Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a durable, cloud-embedded Qdrant retrieval layer that supplies minimal writing and risk-guard context plus immutable, author-visible source snapshots to the existing Studio.

**Architecture:** Domain tables remain the only source of truth. Canonical changes enqueue per-novel indexing jobs; a separate worker turns deterministic source records into `text-embedding-v4` dense+sparse Qdrant points. `ContextPackageService` calls a retrieval facade that fuses and reranks tenant-filtered candidates, projects writer/guard packages, and freezes the selected source contract on every WritingRun.

**Tech Stack:** Python 3.12, FastAPI, async SQLAlchemy, Alembic, httpx, `qdrant-client`, Qdrant Docker, Alibaba Cloud Model Studio `text-embedding-v4` / `qwen3-rerank`, Vue 3, TypeScript, Vitest.

## Global Constraints

- Use one shared Qdrant collection named `novel-context-v1`; every point and every query must filter `tenant_key = "{user_id}:{novel_id}"`.
- Qdrant is derived data only. Never let an API, editor, or source detail read Qdrant as the system of record.
- Use `text-embedding-v4` with `dimension=1024`, `output_type="dense&sparse"`, and `text_type="document"` for indexed text / `"query"` for retrieval queries.
- Use `qwen3-rerank` only after hybrid recall. Cap both Model Studio requests and context budgets.
- Index only locked chapters and confirmed canonical memories. Never index WorkingCopy, draft chapters, unconfirmed PendingMemory, or an AI candidate revision.
- Keep hidden foreshadowing truth out of writer context. It may enter guard context only as a minimized prohibition.
- `WritingRun.context_snapshot_json.source_items` uses the existing six-field `StudioSourceOut` contract; diagnostics are stored beside it, not inserted into prose or shown by default.
- Async indexing must survive API restart: write a database job after a successful domain commit and process it only in `python -m app.retrieval.worker`.
- Preserve the user-owned dirty `frontend/components.d.ts` and untracked `.superpowers/brainstorm/`; do not stage either.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `docker-compose.yml` | Qdrant-only local service, loopback port binding and persistent volume. |
| `backend/requirements.txt` | Adds the async Qdrant client. |
| `backend/.env.example`, `backend/app/core/config.py` | Retrieval endpoint, collection, Model Studio and feature-switch settings; no secret defaults. |
| `backend/app/models/retrieval.py` | Durable `RetrievalIndexJob` ORM model. |
| `backend/alembic/versions/*_phase_5_retrieval.py` | Production schema for retrieval jobs. |
| `backend/app/repositories/retrieval_index_repo.py` | Job dedupe, leasing, completion/retry and status queries. |
| `backend/app/services/retrieval_index_service.py` | Ownership-aware enqueue, rebuild, purge and status API façade. |
| `backend/app/retrieval/contracts.py` | Typed source, embedding, vector-store and retrieval-result contracts. |
| `backend/app/retrieval/model_studio.py` | Async HTTP Model Studio embedding/rerank client and error normalization. |
| `backend/app/retrieval/qdrant_store.py` | Collection initialization, point CRUD, tenant-filtered hybrid RRF query. |
| `backend/app/retrieval/source_builder.py` | Canonical model → stable source records, scene chunking and hashes. |
| `backend/app/retrieval/indexer.py` | Per-novel Qdrant synchronization and stale-point deletion. |
| `backend/app/retrieval/service.py` | Candidate fusion/rerank output, source budgets, writer/guard projection and fallback. |
| `backend/app/retrieval/worker.py` | Polling worker CLI using the persistent job repository. |
| `backend/app/api/retrieval.py`, `backend/app/schemas/retrieval.py` | Index status and rebuild endpoints. |
| `backend/app/services/context_package_service.py`, `backend/app/services/writing_service.py` | Retrieval-enriched ContextPackage construction and immutable run snapshots. |
| `backend/app/services/{novel_service,memory_service}.py`, `backend/app/ai/router.py` | Enqueue sync/purge only after canonical state commits. |
| `backend/app/main.py`, `backend/app/models/__init__.py`, `backend/alembic/env.py` | Register model and router. |
| `backend/tests/test_phase_5_retrieval.py` | Fake-provider unit/integration tests for all retrieval behavior. |
| `frontend/src/types/writingStudio.ts`, `frontend/src/components/studio/StudioSourcesPanel.vue` | Match the existing backend source snapshot contract and hide diagnostics by default. |
| `frontend/src/__tests__/StudioView.spec.ts` | Source-panel contract regression coverage. |

## Task 1: Durable job model, configuration, and local Qdrant service

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/app/models/retrieval.py`
- Create: `backend/alembic/versions/b1c2d3e4f5a6_phase_5_retrieval.py`
- Create: `backend/app/repositories/retrieval_index_repo.py`
- Create: `backend/app/services/retrieval_index_service.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/test_phase_5_retrieval.py`

**Interfaces:**
- Produces `RetrievalIndexJob`, `RetrievalIndexRepo`, and `RetrievalIndexService` for all later tasks.
- `enqueue_sync(novel_id: int, user_id: int) -> RetrievalIndexJob`, `enqueue_purge(novel_id: int, user_id: int) -> RetrievalIndexJob`, `request_rebuild(novel_id: int, user_id: int) -> RetrievalIndexJob` and `status(novel_id: int, user_id: int) -> RetrievalIndexJob | None` are the only service entry points for domain/API code.
- `claim_next(now: datetime) -> RetrievalIndexJob | None` obtains a lease; `complete(job)`, `retry(job, error)`, and `fail(job, error)` own all state transitions.

- [ ] **Step 1: Write failing job lifecycle tests**

```python
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


async def make_user_and_novel(db):
    user = User(email="retrieval@example.com", password_hash="hash")
    db.add(user)
    await db.flush()
    novel = Novel(user_id=user.id, title="检索测试小说")
    db.add(novel)
    await db.commit()
    return user, novel
```

- [ ] **Step 2: Run the focused tests to prove the missing contracts**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py -x -q`

Expected: FAIL during collection because `app.models.retrieval` and `RetrievalIndexService` do not exist.

- [ ] **Step 3: Add configuration, Docker service, and package dependency**

Add `qdrant-client>=1.18.0,<1.19.0` to `backend/requirements.txt`, keeping its minor version aligned with the Docker image. Keep `httpx`, already present, for Model Studio HTTP calls. Add exactly these non-secret environment variables to `.env.example` and `Settings` (with the shown safe values):

```text
RETRIEVAL_ENABLED=true
QDRANT_URL=http://127.0.0.1:6333
QDRANT_COLLECTION=novel-context-v1
MODEL_STUDIO_BASE_URL=
MODEL_STUDIO_API_KEY=
MODEL_STUDIO_EMBEDDING_MODEL=text-embedding-v4
MODEL_STUDIO_RERANK_MODEL=qwen3-rerank
```

Create the root Compose file without an API service, because this repository has no backend container image yet:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:v1.18.0
    ports:
      - '127.0.0.1:6333:6333'
    volumes:
      - qdrant_storage:/qdrant/storage
    healthcheck:
      test: ['CMD', '/bin/bash', '-c', "exec 3<>/dev/tcp/127.0.0.1/6333 && printf 'GET /healthz HTTP/1.0\\r\\n\\r\\n' >&3 && IFS= read -r status <&3 && [[ \"$$status\" == *' 200 '* ]]"]
      interval: 10s
      timeout: 3s
      retries: 10

volumes:
  qdrant_storage:
```

- [ ] **Step 4: Implement the model and repository with explicit state transitions**

`RetrievalIndexJob` has no foreign key to `novels`, so a queued purge can outlive the novel row. It has nullable `novel_id`, required `tenant_key`, `operation`, `status`, `attempt_count`, `next_attempt_at`, `lease_expires_at`, `last_error`, and timestamps. Use these literal sets:

```python
OPERATIONS = {"sync", "rebuild", "purge"}
ACTIVE_STATUSES = {"pending", "running", "retry_wait"}

async def claim_next(self, now: datetime.datetime) -> RetrievalIndexJob | None:
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
```

`retry()` increments attempts, uses `min(300, 2 ** attempt_count)` seconds, clears the lease, and transitions to `failed` after five attempts. `enqueue_sync()` and `request_rebuild()` return the existing active job for the same `tenant_key`; `enqueue_purge()` creates/returns a purge job with the precomputed tenant key.

Register the model in both `app/models/__init__.py` and Alembic `env.py`; write an Alembic migration with all columns/indexes instead of relying on development `create_all`.

- [ ] **Step 5: Re-run focused tests and migration checks**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py -x -q && .venv/bin/python -m alembic upgrade head`

Expected: job tests pass and Alembic exits 0.

- [ ] **Step 6: Commit this independently testable slice**

```bash
git add docker-compose.yml backend/requirements.txt backend/.env.example \
  backend/app/core/config.py backend/app/models/retrieval.py \
  backend/app/models/__init__.py backend/alembic/env.py \
  backend/alembic/versions/b1c2d3e4f5a6_phase_5_retrieval.py \
  backend/app/repositories/retrieval_index_repo.py \
  backend/app/services/retrieval_index_service.py backend/tests/test_phase_5_retrieval.py
git commit -m "feat: add retrieval index job foundation"
```

## Task 2: Model Studio and Qdrant adapters behind testable contracts

**Files:**
- Create: `backend/app/retrieval/__init__.py`
- Create: `backend/app/retrieval/contracts.py`
- Create: `backend/app/retrieval/model_studio.py`
- Create: `backend/app/retrieval/qdrant_store.py`
- Modify: `backend/tests/test_phase_5_retrieval.py`

**Interfaces:**
- Consumes settings from Task 1.
- Produces `EmbeddingProvider.embed_documents()`, `EmbeddingProvider.embed_query()`, `Reranker.rerank()`, and `VectorStore` methods used by Tasks 3–5.
- Raises `RetrievalUnavailable` for every remote/model/store failure; callers must never receive raw provider exceptions or credentials.

- [ ] **Step 1: Write failing adapter-contract tests with fake HTTP transport**

```python
@pytest.mark.asyncio
async def test_model_studio_requests_dense_sparse_documents_and_query():
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"output": {"embeddings": [{
            "embedding": [0.1] * 1024,
            "sparse_embedding": {"indices": [7], "values": [0.8]},
        }]}})

    client = ModelStudioClient(settings=fake_settings(), http=httpx.AsyncClient(
        transport=httpx.MockTransport(handler)))
    await client.embed_documents(["沈砚发现账册"])
    await client.embed_query("军饷账册与沈砚")

    assert captured[0].json()["parameters"] == {
        "dimension": 1024, "output_type": "dense&sparse", "text_type": "document"
    }
    assert captured[1].json()["parameters"]["text_type"] == "query"


@pytest.mark.asyncio
async def test_model_studio_rerank_uses_qwen3_result_indices():
    # The provider returns source positions in qwen3-rerank score order.
    client = ModelStudioClient(settings=fake_settings(), http=client_returning(
        {"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}]}
    ))
    assert [item.index for item in await client.rerank("军饷", ["旧事", "账册"])] == [1, 0]
```

- [ ] **Step 2: Run the focused test file**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py -x -q`

Expected: FAIL because `app.retrieval.contracts` and `ModelStudioClient` do not exist.

- [ ] **Step 3: Define provider/store contracts and Model Studio HTTP client**

Use typed dataclasses and protocols; no retrieval service may import an SDK-specific result type:

```python
@dataclass(frozen=True)
class HybridEmbedding:
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]

@dataclass(frozen=True)
class RerankResult:
    index: int
    score: float

class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[HybridEmbedding]: ...
    async def embed_query(self, text: str) -> HybridEmbedding: ...

class Reranker(Protocol):
    async def rerank(self, query: str, documents: list[str]) -> list[RerankResult]: ...
```

Use `httpx.AsyncClient.post` against `${MODEL_STUDIO_BASE_URL}/services/embeddings/text-embedding/text-embedding` with `Authorization: Bearer ...`, batches of at most ten texts, and the `parameters` asserted above. For `qwen3-rerank`, derive the compatible API base from the configured Model Studio host and call `https://{host}/compatible-api/v1/reranks` with the root-level shape:

```python
payload = {
    "model": settings.MODEL_STUDIO_RERANK_MODEL,
    "query": query,
    "documents": documents,
    "top_n": len(documents),
    "instruct": "Retrieve novel canon passages relevant to the current writing task.",
}
```

Validate exactly 1024 dense values and normalize Model Studio sparse token records into paired Qdrant indices/values; normalize HTTP/timeouts/invalid payloads into `RetrievalUnavailable("检索服务暂不可用")` while logging only status code and request ID.

- [ ] **Step 4: Implement Qdrant collection and hybrid-query adapter**

Create a `QdrantVectorStore` around `AsyncQdrantClient`. `ensure_collection()` creates named `dense`/`sparse` vectors and payload indexes only when absent. `hybrid_search()` must create one filter internally and pass it to both prefetches:

```python
tenant_filter = models.Filter(must=[models.FieldCondition(
    key="tenant_key", match=models.MatchValue(value=tenant_key),
)])
result = await self.client.query_points(
    collection_name=self.collection,
    prefetch=[
        models.Prefetch(query=query.dense, using="dense", filter=tenant_filter, limit=dense_limit),
        models.Prefetch(
            query=models.SparseVector(indices=query.sparse_indices, values=query.sparse_values),
            using="sparse", filter=tenant_filter, limit=sparse_limit,
        ),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    limit=limit,
    with_payload=True,
)
```

Expose `upsert(points)`, `list_indexed_sources(tenant_key)`, `delete_point_ids(ids)`, `delete_tenant(tenant_key)`, and `hybrid_search(...)`. Convert Qdrant exceptions to `RetrievalUnavailable`; do not log vectors or point text.

- [ ] **Step 5: Re-run adapter tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py -x -q`

Expected: adapter contract tests pass without network access.

- [ ] **Step 6: Commit the external adapters**

```bash
git add backend/app/retrieval backend/tests/test_phase_5_retrieval.py
git commit -m "feat: add retrieval provider and vector store adapters"
```

## Task 3: Canonical source builder and idempotent novel indexer

**Files:**
- Create: `backend/app/retrieval/source_builder.py`
- Create: `backend/app/retrieval/indexer.py`
- Modify: `backend/tests/test_phase_5_retrieval.py`

**Interfaces:**
- Consumes `EmbeddingProvider` and `VectorStore` from Task 2.
- Produces `CanonicalSourceBuilder.build(novel_id, user_id) -> list[RetrievalSource]` and `NovelIndexer.sync(novel_id, user_id) -> IndexSyncResult` for the worker.

- [ ] **Step 1: Write failing canonical-source and stale-point tests**

```python
@pytest.mark.asyncio
async def test_source_builder_indexes_only_locked_canon_and_hides_foreshadow_truth(db):
    user, novel = await make_user_and_novel(db)
    locked = await add_chapter(db, novel, status="locked", content="甲。\n\n乙。")
    await add_chapter(db, novel, status="draft", content="不能入索引")
    await add_foreshadowing(db, novel, locked.id, description="雨夜铃声", hidden_truth="凶手身份")

    sources = await CanonicalSourceBuilder(db).build(novel.id, user.id)
    assert {item.source_type for item in sources} >= {"chapter_summary", "chapter_scene", "foreshadowing_signal", "foreshadowing_guard"}
    assert all("不能入索引" not in item.text for item in sources)
    assert next(item for item in sources if item.source_type == "foreshadowing_signal").text.find("凶手身份") == -1
    assert "凶手身份" in next(item for item in sources if item.source_type == "foreshadowing_guard").text


@pytest.mark.asyncio
async def test_indexer_deletes_changed_point_before_upserting_replacement(db):
    store, embedder = FakeVectorStore(), FakeEmbeddingProvider()
    indexer = NovelIndexer(db, embedder=embedder, store=store)
    await indexer.sync(novel_id=1, user_id=1)
    await change_locked_source(db)
    await indexer.sync(novel_id=1, user_id=1)
    assert store.delete_calls[0] == [store.original_point_id]
    assert store.current_source_hashes_are_fresh()
```

- [ ] **Step 2: Run the source/indexer tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py -x -q`

Expected: FAIL because the builder and indexer are absent.

- [ ] **Step 3: Implement stable source records and scene chunking**

Define `RetrievalSource` with `source_id`, `source_type`, `source_record_id`, `chapter_id`, `title`, `text`, `preview`, `visibility`, `locator`, `content_hash`, and `tenant_key`. Use exactly these identifiers:

```python
f"chapter:{chapter.id}:summary"
f"chapter:{chapter.id}:scene:{scene_index}"
f"character:{character.id}"
f"plot_fact:{fact.id}"
f"world_setting:{setting.id}"
f"foreshadowing:{item.id}:signal"
f"foreshadowing:{item.id}:guard"
```

Split a locked chapter by blank-line scene boundaries, then combine paragraphs until 700 Chinese characters and carry the final 120 characters into the next chunk. The signal text contains name/description/status only. Guard text may contain hidden truth/risk warning and is always `visibility="guard"`. Generate `content_hash = sha256(normalized_text.encode()).hexdigest()` and deterministic UUID5 point IDs using `tenant_key`, `source_id`, hash, and `"v1"`.

- [ ] **Step 4: Implement cost-safe synchronization**

`NovelIndexer.sync()` first asks the store for `{point_id, source_id, content_hash}` for the tenant. It deletes every stored point whose source is gone or whose hash changed, then embeds only new/changed sources in batches of ten and upserts their point records. This order prevents deleting the newly inserted replacement point:

```python
old_by_source = {item.source_id: item for item in await self.store.list_indexed_sources(tenant_key)}
to_delete = [old.point_id for source_id, old in old_by_source.items()
             if source_id not in current_by_source
             or old.content_hash != current_by_source[source_id].content_hash]
if to_delete:
    await self.store.delete_point_ids(to_delete)
to_upsert = [source for source in sources
             if source.source_id not in old_by_source
             or old_by_source[source.source_id].content_hash != source.content_hash]
```

The worker will call `delete_tenant()` for purge, never `sync()` after a novel has been deleted.

- [ ] **Step 5: Run the task tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py -x -q`

Expected: canonical source, hash, stale-delete, and no-draft assertions pass.

- [ ] **Step 6: Commit source materialization**

```bash
git add backend/app/retrieval/source_builder.py backend/app/retrieval/indexer.py \
  backend/tests/test_phase_5_retrieval.py
git commit -m "feat: index canonical novel retrieval sources"
```

## Task 4: Worker, mutation enqueue points, and index-control API

**Files:**
- Create: `backend/app/retrieval/worker.py`
- Create: `backend/app/api/retrieval.py`
- Create: `backend/app/schemas/retrieval.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/novel_service.py`
- Modify: `backend/app/services/memory_service.py`
- Modify: `backend/app/ai/router.py`
- Modify: `backend/tests/test_phase_5_retrieval.py`

**Interfaces:**
- Consumes jobs from Task 1 and indexer from Task 3.
- Produces `python -m app.retrieval.worker`, `GET /novels/{novel_id}/retrieval-index`, and `POST /novels/{novel_id}/retrieval-index/rebuild`.

- [ ] **Step 1: Write failing worker, enqueue, ownership, and API tests**

```python
@pytest.mark.asyncio
async def test_worker_completes_sync_and_retries_unavailable_job(db):
    job = await RetrievalIndexService(db).enqueue_sync(novel_id=1, user_id=1)
    worker = RetrievalWorker(session_factory=fake_session_factory(db), indexer=FakeIndexer())
    assert await worker.run_once() is True
    assert job.status == "completed"


@pytest.mark.asyncio
async def test_publish_and_confirmed_memory_enqueue_sync(client, novel_and_headers):
    novel_id, headers = novel_and_headers
    await publish_chapter(client, novel_id, headers)
    await confirm_pending_memory(client, novel_id, headers)
    assert await pending_sync_job_count(novel_id) == 1


@pytest.mark.asyncio
async def test_rebuild_endpoint_hides_other_users_novel(client, two_users_two_novels):
    response = await client.post("/api/v1/novels/2/retrieval-index/rebuild", headers=user_one_headers)
    assert response.status_code == 404
```

- [ ] **Step 2: Run the focused test file**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py -x -q`

Expected: FAIL because worker/router do not exist and canonical mutations do not enqueue jobs.

- [ ] **Step 3: Implement worker lease processing**

The worker loop has no FastAPI dependency and commits each transition separately:

```python
class RetrievalWorker:
    async def run_once(self) -> bool:
        async with self.session_factory() as db:
            repo = RetrievalIndexRepo(db)
            job = await repo.claim_next(datetime.datetime.now())
            if job is None:
                return False
            await db.commit()
            try:
                if job.operation == "purge":
                    await self.indexer.purge(job.tenant_key)
                else:
                    user_id = int(job.tenant_key.split(":", maxsplit=1)[0])
                    await self.indexer.sync(job.novel_id, user_id)
            except RetrievalUnavailable as exc:
                await repo.retry(job, str(exc))
            except Exception:
                logger.exception("Retrieval index job %s failed", job.id)
                await repo.retry(job, "索引任务失败")
            else:
                await repo.complete(job)
            await db.commit()
            return True
```

`main()` repeatedly calls `run_once()` and sleeps one second only when no job is claimed. It must be executable with `python -m app.retrieval.worker`.

- [ ] **Step 4: Enqueue strictly after canonical commits**

After `NovelService.publish_chapter()` commits a locked chapter, call `enqueue_sync()`. For chapter update/delete, enqueue whenever the operation can add/remove/change a locked chapter. After every character/world-setting CRUD success in `MemoryService`, enqueue sync. In both single and batch PendingMemory confirmation routes, enqueue once after all confirmations for that novel succeed. Before `NovelService.delete()` calls the repository delete, enqueue the purge job using the already-authorized user and novel IDs, commit the job, then delete the novel.

Do not enqueue for draft autosave, WritingRun generation, pending-memory creation, rejection, or failed transactions.

- [ ] **Step 5: Add ownership-safe API and register it**

Use two Pydantic output objects:

```python
class RetrievalIndexStatusOut(BaseModel):
    status: str
    operation: str
    requested_at: datetime | None
    completed_at: datetime | None
    last_error: str | None

class RetrievalRebuildOut(BaseModel):
    job_id: int
    status: str
```

Both routes first call the retrieval index service, which calls `MemoryService.ensure_owned_novel()` semantics (NotFound for missing or foreign novel). Register `retrieval.router` in `app/main.py`; return existing `ApiResponse.success` envelopes.

- [ ] **Step 6: Run task tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py -x -q`

Expected: worker lifecycle, all enqueue paths, and both endpoint authorization cases pass.

- [ ] **Step 7: Commit worker and control plane**

```bash
git add backend/app/retrieval/worker.py backend/app/api/retrieval.py \
  backend/app/schemas/retrieval.py backend/app/main.py \
  backend/app/services/novel_service.py backend/app/services/memory_service.py \
  backend/app/ai/router.py backend/tests/test_phase_5_retrieval.py
git commit -m "feat: process and control retrieval indexing"
```

## Task 5: Hybrid retrieval service with writer/guard separation and fallback

**Files:**
- Create: `backend/app/retrieval/service.py`
- Modify: `backend/app/retrieval/contracts.py`
- Modify: `backend/tests/test_phase_5_retrieval.py`

**Interfaces:**
- Consumes the Task 2 provider/store contracts.
- Produces `RetrievalService.retrieve(request: RetrievalRequest) -> RetrievalContext` used by Task 6.
- `RetrievalContext.writer_items`, `guard_constraints`, `source_items`, and `diagnostics` are the complete result contract.

- [ ] **Step 1: Write failing retrieval behavior tests**

```python
@pytest.mark.asyncio
async def test_retrieval_uses_tenant_filter_reranks_and_limits_duplicate_scenes():
    store = FakeVectorStore(points=canonical_points_for_two_novels())
    result = await RetrievalService(FakeEmbeddingProvider(), FakeReranker([2, 0, 1]), store).retrieve(
        RetrievalRequest(user_id=1, novel_id=1, query="沈砚与军饷账册", target_chapter_id=19)
    )
    assert store.filters == [("1:1", "writer"), ("1:1", "guard")]
    assert [item["source_id"] for item in result.source_items][:2] == ["chapter:18:scene:3", "character:7"]
    assert sum(item["locator"].get("chapter_id") == 18 for item in result.writer_items) <= 2


@pytest.mark.asyncio
async def test_guard_never_leaks_hidden_truth_into_writer_context_and_provider_failure_falls_back():
    result = await failing_retrieval_service().retrieve(request_for_novel_one())
    assert result.writer_items == []
    assert result.guard_constraints == []
    assert result.diagnostics["retrieval_status"] == "fallback"
```

- [ ] **Step 2: Run the new tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py -x -q`

Expected: FAIL because `RetrievalService` and its result types do not exist.

- [ ] **Step 3: Implement retrieve, rerank, diversity, and snapshot projection**

Use fixed limits from the approved design: dense/sparse recall 24 each, fusion 20, final writer 10, final guard 6. Run the store once with `visibility="writer"` and once with `visibility="guard"`; each call uses the same tenant-only request context. Rerank only the fused candidates and preserve the rerank order by its returned input indices.

Use this source projection and do not add score fields to `source_items`:

```python
def to_source_item(item: RetrievedSource, reason: str) -> dict:
    return {
        "source_id": item.source_id,
        "source_type": item.source_type,
        "title": item.title,
        "locator": item.locator,
        "preview": item.preview,
        "inclusion_reason": reason,
    }
```

Apply in order: reject duplicate `source_id`; permit at most two `chapter_scene` items per chapter; then take high-importance atomic facts/settings before lower-ranked duplicate scenes; stop at the item and estimated-token budgets. `guard_constraints` must be generated from guard source name/status/risk wording without appending `hidden_truth` to writer items. Put raw candidate scores, source IDs, collection version, and failure reason only in `diagnostics`.

Catch `RetrievalUnavailable` at this façade boundary and return empty retrieval lists plus `{"retrieval_status": "fallback", "reason": "service_unavailable"}`. Do not catch programmer errors or falsely report retrieved sources.

- [ ] **Step 4: Run task tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py -x -q`

Expected: tenant filtering, score order, diversity, hidden-truth separation, and fallback tests pass.

- [ ] **Step 5: Commit retrieval assembly**

```bash
git add backend/app/retrieval/contracts.py backend/app/retrieval/service.py \
  backend/tests/test_phase_5_retrieval.py
git commit -m "feat: retrieve canon context with guard separation"
```

## Task 6: Enrich ContextPackage and freeze sources on every WritingRun path

**Files:**
- Modify: `backend/app/services/context_package_service.py`
- Modify: `backend/app/services/writing_service.py`
- Modify: `backend/tests/test_phase_5_retrieval.py`
- Modify: `backend/tests/test_phase_1_writing.py`
- Modify: `backend/tests/test_phase_3_dynamic_plot_planning.py`

**Interfaces:**
- Consumes `RetrievalService.retrieve()` from Task 5.
- Produces `package["retrieved_context"]`, `package["risk_guard"]`, and `package["snapshot"]` with `source_items`/`diagnostics` for Task 7 and the existing AI generator.

- [ ] **Step 1: Add failing integration tests for both legacy and planned writing paths**

```python
@pytest.mark.asyncio
async def test_context_package_includes_retrieval_and_safe_guard_snapshot(db, monkeypatch):
    service = ContextPackageService(db, user_id=1, novel_id=1, retrieval=FakeRetrievalService())
    package = await service.build_for_brief(brief_id=1, plot_plan_revision_id=1, author_input="军饷")
    assert package["retrieved_context"][0]["source_id"] == "chapter:18:scene:3"
    assert package["risk_guard"][0]["constraint"].startswith("本章不可")
    assert package["snapshot"]["source_items"][0]["source_id"] == "chapter:18:scene:3"
    assert "hidden_truth" not in str(package["retrieved_context"])


@pytest.mark.asyncio
async def test_every_writing_run_copies_context_snapshot_even_without_plot_plan(db):
    run = await WritingService(db, 1, 1, generator=FakeWritingGenerator()).create_writing_run(brief_id=1)
    assert run.context_snapshot_json["source_items"] == [{
        "source_id": "character:7", "source_type": "character_profile", "title": "沈砚",
        "locator": {"character_id": 7}, "preview": "当前状态", "inclusion_reason": "角色连续性"
    }]
```

- [ ] **Step 2: Run the affected test files**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py tests/test_phase_1_writing.py tests/test_phase_3_dynamic_plot_planning.py -x -q`

Expected: FAIL because existing package builders do not call retrieval and legacy runs leave snapshots empty.

- [ ] **Step 3: Add one package-enrichment helper and use it in both builders**

Add a `ContextRetrievalEnricher` (or injected `RetrievalService`) that accepts the baseline package plus user/novel IDs, brief, plan and author input. Build a deterministic query from `author_input`, brief JSON, plan JSON, plot-unit title and recent summary. Add only these fields:

```python
package["retrieved_context"] = retrieval.writer_items
package["risk_guard"] = retrieval.guard_constraints
package["snapshot"] = {
    **package.get("snapshot", {}),
    "source_items": retrieval.source_items,
    "diagnostics": retrieval.diagnostics,
}
```

Call the helper in `ContextPackageService.build_for_brief()` and the legacy `WritingService._build_context_package()` path. Preserve current author foundation, chapter brief, plot plan, length contract, latest summary, and style guide as structured anchors. Retrieval supplements/replaces only full-history lists; it must not remove the active brief or plan.

- [ ] **Step 4: Freeze the snapshot for all run creation paths**

Immediately after `run_repo.create(...)`, assign the package snapshot unconditionally:

```python
run.context_snapshot_json = copy.deepcopy(package.get("snapshot", {
    "source_items": [], "diagnostics": {"retrieval_status": "not_requested"},
}))
await self.db.flush()
```

Remove the current `if plot_plan_revision_id is not None` guard around this assignment. Never mutate `run.context_snapshot_json` after draft generation, quality-gate retries, index rebuild, or source changes.

- [ ] **Step 5: Run regression tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py tests/test_phase_1_writing.py tests/test_phase_3_dynamic_plot_planning.py tests/test_phase_6_author_studio.py -x -q`

Expected: all pass, including old Studio source snapshot tests.

- [ ] **Step 6: Commit ContextPackage integration**

```bash
git add backend/app/services/context_package_service.py backend/app/services/writing_service.py \
  backend/tests/test_phase_5_retrieval.py backend/tests/test_phase_1_writing.py \
  backend/tests/test_phase_3_dynamic_plot_planning.py
git commit -m "feat: enrich writing context with retrieval snapshots"
```

## Task 7: Align Studio source types and preserve author-facing diagnostics boundary

**Files:**
- Modify: `frontend/src/types/writingStudio.ts`
- Modify: `frontend/src/components/studio/StudioSourcesPanel.vue`
- Modify: `frontend/src/__tests__/StudioView.spec.ts`
- Modify: `backend/tests/test_phase_6_author_studio.py`

**Interfaces:**
- Consumes the six-field `StudioSourceOut` already returned by `/writing-runs/{run_id}/sources`.
- Produces a source panel that presents title, preview and reason only; source diagnostics remain server-side snapshot metadata and are not part of this endpoint.

- [ ] **Step 1: Write the failing TypeScript contract test/update fixture**

Add this fixture to the Studio test and assert the panel renders the stable source key/text:

```ts
const sourceFixture: StudioSource = {
  source_id: 'chapter:18:scene:3',
  source_type: 'chapter_scene',
  title: '第 18 章 · 第 3 场',
  locator: { chapter_id: 18, scene_index: 3 },
  preview: '沈砚发现军饷账册异常。',
  inclusion_reason: '与当前角色认知和军饷案直接相关',
}
```

Also extend the backend source test to verify an older run returns its stored `source_items` after a newer ContextPackage is created.

- [ ] **Step 2: Run the focused frontend and backend tests to prove the mismatch**

Run: `cd frontend && npm run test:unit -- --run src/__tests__/StudioView.spec.ts && npm run type-check`

Expected: FAIL because `StudioSource` incorrectly requires `id`, `writing_run_id`, `relevance_score`, and `diagnostics` instead of the backend contract.

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_6_author_studio.py -x -q`

Expected: PASS before the added immutability regression; then FAIL until the test is implemented.

- [ ] **Step 3: Make the TypeScript model exactly mirror `StudioSourceOut`**

Replace the existing frontend interface with:

```ts
export interface StudioSource {
  source_id: string
  source_type: string
  title: string
  locator: Record<string, unknown>
  preview: string
  inclusion_reason: string
}
```

Update the panel to key and test-id from `source.source_id`, retain only title/preview/reason, and remove the per-item `diagnostics` collapse because the API intentionally does not return it. Do not manually edit generated `frontend/components.d.ts`; let the project’s auto-import tooling update it when the verification command runs.

- [ ] **Step 4: Run focused verification**

Run: `cd frontend && npm run test:unit -- --run src/__tests__/StudioView.spec.ts && npm run type-check`

Expected: Vitest and vue-tsc both exit 0.

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py tests/test_phase_6_author_studio.py -x -q`

Expected: historical source snapshots remain immutable and API serialization agrees with the frontend contract.

- [ ] **Step 5: Commit source presentation alignment**

```bash
git add frontend/src/types/writingStudio.ts frontend/src/components/studio/StudioSourcesPanel.vue \
  frontend/src/__tests__/StudioView.spec.ts backend/tests/test_phase_6_author_studio.py \
  backend/tests/test_phase_5_retrieval.py
git commit -m "fix: align studio source snapshot contract"
```

## Task 8: Deployment smoke checks, comprehensive verification, and documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-07-16-v2-phase-5-retrieval-design.md`
- Modify: `backend/tests/test_phase_5_retrieval.py`

**Interfaces:**
- Consumes all previous tasks.
- Produces reproducible local startup/rebuild/worker instructions and final evidence that retrieval has not regressed existing phases.

- [ ] **Step 1: Add a compose/config smoke test and operations assertions**

```python
def test_retrieval_configuration_has_no_default_secret():
    assert Settings().MODEL_STUDIO_API_KEY == ""
    assert Settings().QDRANT_COLLECTION == "novel-context-v1"

def test_compose_binds_qdrant_to_loopback():
    compose = Path(__file__).parents[2] / "docker-compose.yml"
    assert "127.0.0.1:6333:6333" in compose.read_text()
    assert "qdrant_storage" in compose.read_text()
```

- [ ] **Step 2: Run the new operational test and Docker configuration check**

Run: `cd backend && .venv/bin/python -m pytest tests/test_phase_5_retrieval.py -x -q && cd .. && docker compose config`

Expected: pytest exits 0; Compose emits resolved YAML without errors. If Docker is unavailable on the machine, record the exact unavailable command and do not claim the container smoke check passed.

- [ ] **Step 3: Document exact local operating procedure**

Add these commands and their intended order to the Phase 5 design document:

```bash
docker compose up -d qdrant
cd backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.retrieval.worker
# in another terminal, request a rebuild through the authenticated API or Studio-adjacent settings
```

Document the required `MODEL_STUDIO_BASE_URL` workspace endpoint and `MODEL_STUDIO_API_KEY`, the fact that Qdrant is loopback-only locally, the fallback behavior, and that old WritingRun sources do not change after rebuilding.

- [ ] **Step 4: Run the complete verification suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -x -q`

Expected: all backend tests pass.

Run: `cd frontend && npm run test:unit && npm run type-check && npm run lint && npm run build`

Expected: all frontend commands exit 0. If generated `components.d.ts` changes during verification, inspect it and stage it only if it is solely the legitimate auto-import regeneration; never overwrite unrelated user changes.

- [ ] **Step 5: Commit documentation and final verification changes**

```bash
git add docs/superpowers/specs/2026-07-16-v2-phase-5-retrieval-design.md \
  backend/tests/test_phase_5_retrieval.py
git commit -m "docs: add phase 5 retrieval operations"
```

## Plan Self-Review

### Spec coverage

| Approved requirement | Plan task(s) |
| --- | --- |
| Qdrant Docker, shared versioned collection and tenant isolation | 1, 2, 8 |
| Model Studio v4 dense+sparse and qwen3-rerank | 2, 5 |
| Layered canonical sources | 3 |
| Durable async indexing, retries, rebuild, purge | 1, 3, 4 |
| Writer context separated from guard context | 3, 5, 6 |
| Failure fallback without blocking writing | 2, 5, 6 |
| Immutable source snapshot on every WritingRun path | 6, 7 |
| Studio source presentation without scores/diagnostics | 7 |
| Ownership, cost, recovery and deployment checks | 1, 4, 5, 8 |

No Phase 5 design requirement is uncovered.

### Placeholder scan

The plan contains no `TODO`, `TBD`, “implement later”, or unspecified-error-handling steps. Remote calls, state transitions, source IDs, payload fields, endpoint paths, test commands, and commit contents are named explicitly.

### Type consistency

- Tasks 2–5 share `HybridEmbedding`, `RerankResult`, `EmbeddingProvider`, `Reranker`, and `VectorStore` from `app/retrieval/contracts.py`.
- Task 3’s `RetrievalSource` becomes Task 5’s `RetrievedSource` payload; `to_source_item()` emits exactly the existing `StudioSourceOut` fields consumed in Tasks 6–7.
- Tasks 1 and 4 use the same `RetrievalIndexJob` and `RetrievalIndexService` API.
- Task 6 owns the only writing-run snapshot assignment; Task 7 reads it without re-querying Qdrant.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-16-v2-phase-5-retrieval.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, with review between tasks.
2. **Inline Execution** — execute tasks in this session using `executing-plans`, in batches with checkpoints.

Which approach?
