# Phase 6 Author Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the split writing workflow and chapter editor with a persistent, full-screen author studio: chapter explorer on the left, document in the middle, and a source-aware AI creation session on the right.

**Architecture:** Add a writing-session persistence layer above the existing `WritingRun`, `ContextPackage`, `DraftVersion`, and `DraftRevision` domain models. `WritingStudioService` records author messages, restricts AI output to a small action vocabulary, and delegates domain mutations to existing services. The Vue Studio route owns the three-pane layout; a dedicated Pinia store coordinates session state and a persisted working copy, while existing writing and revision stores retain their current domain responsibilities.

**Tech Stack:** FastAPI, async SQLAlchemy 2.x, Alembic, Pydantic 2, LangChain/DeepSeek, pytest/pytest-asyncio/httpx, Vue 3, TypeScript, Pinia, Element Plus, Vitest, Playwright, SCSS.

## Global Constraints

- All backend routes remain nested under `/api/v1/novels/{novel_id}/` and return `ApiResponse.success()` envelopes.
- Ownership failures for sessions, messages, runs, working copies, and sources return the existing `NotFound` behavior.
- Existing `WritingRun`, `DraftVersion`, `DraftRevision`, quality-gate, acceptance, and revision APIs remain available throughout this plan.
- The Studio message coordinator must never write Chapter, DraftVersion, or WritingRun records directly when an existing domain service owns that mutation.
- AI action vocabulary is exactly `clarify`, `generate_plan`, `generate_brief`, `generate_context`, `generate_draft`, `review_draft`, `propose_revision`, and `explain_sources`.
- `accept`, `discard`, `apply_revision`, `force_accept`, and `restore_version` require a Studio action-card confirmation endpoint; author text alone cannot perform them.
- Studio v1 is request/response based. It renders `running`, `completed`, `needs_confirmation`, and `failed` messages; it does not add token-streaming transport.
- A WorkingCopy update includes `base_revision_sequence`; a mismatch returns the existing `BadRequest` conflict response and must not overwrite content.
- Source UI reads the immutable `WritingRun.context_snapshot_json.source_items` contract. It must not query the most recent ContextPackage after a run exists.
- Qdrant, Model Studio embeddings, hybrid retrieval, reranking, Docker deployment, and asynchronous indexing are a separate Phase 6 retrieval implementation. This plan consumes the stable `source_items` snapshot contract so that retrieval can be added without changing the Studio UI or session APIs.
- Backend commands run from `backend/`; frontend commands run from `frontend/`.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `backend/app/models/writing_session.py` | SQLAlchemy models for sessions, messages, and persisted working copies. |
| `backend/app/repositories/writing_session_repo.py` | Session/message/working-copy ownership-filtered persistence queries. |
| `backend/app/schemas/writing_studio.py` | Pydantic request/response schemas and action/message literals. |
| `backend/app/services/writing_session_service.py` | Session creation, loading, source projection, and session ownership checks. |
| `backend/app/services/working_copy_service.py` | Debounced-save target and atomic WorkingCopy-to-revision flush behavior. |
| `backend/app/ai/studio_agent.py` | Restricted intent protocol plus production and fake-agent integration point. |
| `backend/app/services/writing_studio_service.py` | Author-message orchestration, idempotency, action dispatch, and domain-service delegation. |
| `backend/app/api/writing_studio.py` | Studio session, message, action, working-copy, and sources REST endpoints. |
| `backend/app/models/writing.py` | Nullable `writing_session_id` on `WritingRun`. |
| `backend/app/models/__init__.py`, `backend/app/main.py` | Model and router registration. |
| `backend/alembic/versions/0a1b2c3d4e5f_phase_6_author_studio.py` | Production migration for the new tables and WritingRun foreign key. |
| `backend/tests/test_phase_6_author_studio.py` | Persistence, ownership, orchestration, sources, WorkingCopy, and API integration tests. |
| `frontend/src/types/writingStudio.ts` | Studio TypeScript contracts matching response schemas. |
| `frontend/src/api/writingStudio.ts` | HTTP client for Studio REST endpoints. |
| `frontend/src/stores/writingStudio.ts` | Session/document/message state and autosave/action methods. |
| `frontend/src/views/studio/StudioView.vue` | Full-screen route-level three-pane coordinator. |
| `frontend/src/components/studio/StudioChapterExplorer.vue` | Left chapter and unaccepted-draft navigator. |
| `frontend/src/components/studio/StudioDocumentPane.vue` | Center title/body editor, autosave status, and version actions. |
| `frontend/src/components/studio/StudioConversationPane.vue` | Right message timeline, input, and action dispatch. |
| `frontend/src/components/studio/StudioMessage.vue` | One role-aware text or structured message renderer. |
| `frontend/src/components/studio/StudioActionCard.vue` | Confirmation-only actions for acceptance, discard, revision, retry, and restore. |
| `frontend/src/components/studio/StudioSourcesPanel.vue` | Immutable source-items panel rendered from a run snapshot. |
| `frontend/src/components/studio/StudioVersionInspector.vue` | Compact wrapper around existing version/revision UI. |
| `frontend/src/router/index.ts` | Studio route and legacy-route redirects. |
| `frontend/src/components/novels/NovelWorkspaceTabs.vue` | Change the existing “写作” tab target to Studio. |
| `frontend/src/views/novels/NovelDetailView.vue` | Direct chapter edit links to Studio. |
| `frontend/src/__tests__/WritingStudioStore.spec.ts` | Pinia/API state behavior tests. |
| `frontend/src/__tests__/StudioView.spec.ts` | Three-pane route, selection, autosave, source, and confirmation-card component tests. |
| `frontend/e2e/studio.spec.ts` | Browser-level Studio route and responsive layout coverage. |

## Task 1: Add Studio persistence models and production migration

**Files:**
- Create: `backend/app/models/writing_session.py`
- Modify: `backend/app/models/writing.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py`
- Create: `backend/alembic/versions/0a1b2c3d4e5f_phase_6_author_studio.py`
- Test: `backend/tests/test_phase_6_author_studio.py`

**Interfaces:**
- Produces: `WritingSession`, `WritingMessage`, and `DraftWorkingCopy` models; nullable `WritingRun.writing_session_id`.
- Consumes: existing `Novel`, `Chapter`, `WritingRun`, and `DraftVersion` IDs.

- [ ] **Step 0: Add the test-data helper used by every backend Studio test**

At the top of `test_phase_6_author_studio.py`, add this helper instead of relying on non-existent global `novel`, `user`, or run fixtures:

```python
from app.core.security import create_token
from app.models.draft_version import DraftVersion
from app.models.novel import Novel
from app.models.user import User
from app.models.writing import ChapterBrief, ChapterPlan, ContextPackage, WritingRun
from app.services.draft_version_service import DraftVersionService

async def _make_studio_run(db, content: str = "初稿正文"):
    user = User(username="studio_author", hashed_password="x")
    db.add(user)
    await db.flush()
    novel = Novel(title="Studio 测试小说", description="", genre="古风", style_guide="第三人称", user_id=user.id)
    db.add(novel)
    await db.flush()
    plan = ChapterPlan(novel_id=novel.id, position=1)
    db.add(plan)
    await db.flush()
    brief = ChapterBrief(novel_id=novel.id, chapter_plan_id=plan.id)
    db.add(brief)
    await db.flush()
    context = ContextPackage(novel_id=novel.id, chapter_brief_id=brief.id)
    db.add(context)
    await db.flush()
    run = WritingRun(
        novel_id=novel.id, chapter_brief_id=brief.id, context_package_id=context.id,
        status="completed", draft_content=content, word_count=len(content),
        context_snapshot_json={"source_items": [{
            "source_id": "chapter:18:scene:3", "source_type": "chapter_scene",
            "title": "第 18 章 · 第 3 场", "locator": {"chapter_id": 18, "scene_index": 3},
            "preview": "沈砚发现账册异常", "inclusion_reason": "避免越过角色认知",
        }]},
    )
    db.add(run)
    await db.flush()
    version = await DraftVersionService(db, user.id, novel.id).ensure_initial_version(run)
    return user, novel, run, version
```

- [ ] **Step 1: Write failing model persistence tests**

```python
@pytest.mark.asyncio
async def test_session_message_and_working_copy_persist(db):
    from app.models.writing_session import DraftWorkingCopy, WritingMessage, WritingSession
    _, novel, completed_run, draft_version = await _make_studio_run(db)

    session = WritingSession(novel_id=novel.id, active_writing_run_id=completed_run.id,
                             title="第十八章草稿", status="active")
    db.add(session)
    await db.flush()
    db.add(WritingMessage(session_id=session.id, role="author", message_type="text",
                          content_json={"text": "让结尾更克制"}, action_status="completed"))
    db.add(DraftWorkingCopy(writing_run_id=completed_run.id, draft_version_id=draft_version.id,
                            title="第十八章", content=draft_version.content,
                            base_revision_sequence=0))
    await db.commit()

    assert session.id is not None
    assert (await db.get(DraftWorkingCopy, completed_run.id)).content == draft_version.content


@pytest.mark.asyncio
async def test_writing_run_session_link_is_optional_for_legacy_rows(db):
    _, _, completed_run, _ = await _make_studio_run(db)
    await db.refresh(completed_run)
    assert completed_run.writing_session_id is None
```

- [ ] **Step 2: Run the model test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_phase_6_author_studio.py -k persist -x -q`

Expected: FAIL because `app.models.writing_session` and `WritingRun.writing_session_id` do not exist.

- [ ] **Step 3: Implement the models and migration**

```python
# backend/app/models/writing_session.py
class WritingSession(Base):
    __tablename__ = "writing_sessions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    target_chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    active_writing_run_id: Mapped[int | None] = mapped_column(ForeignKey("writing_runs.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="新创作会话")
    status: Mapped[str] = mapped_column(nullable=False, default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

class WritingMessage(Base):
    __tablename__ = "writing_messages"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("writing_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(nullable=False)
    message_type: Mapped[str] = mapped_column(nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    action_status: Mapped[str] = mapped_column(nullable=False, default="completed")
    idempotency_key: Mapped[str | None] = mapped_column(nullable=True, unique=True)
    writing_run_id: Mapped[int | None] = mapped_column(ForeignKey("writing_runs.id"), nullable=True)
    context_package_id: Mapped[int | None] = mapped_column(ForeignKey("context_packages.id"), nullable=True)
    draft_version_id: Mapped[int | None] = mapped_column(ForeignKey("draft_versions.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)

class DraftWorkingCopy(Base):
    __tablename__ = "draft_working_copies"
    writing_run_id: Mapped[int] = mapped_column(ForeignKey("writing_runs.id"), primary_key=True)
    draft_version_id: Mapped[int] = mapped_column(ForeignKey("draft_versions.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_revision_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)
```

Add `writing_session_id = mapped_column(ForeignKey("writing_sessions.id"), nullable=True, index=True)` to `WritingRun`. Register the three models in `app/models/__init__.py`, import them in `app/main.py` so development startup creates the tables, and create the Alembic migration with `down_revision = "f3a4b5c6d7e8"`. The migration creates the three tables and adds/drops the nullable WritingRun foreign key in upgrade/downgrade.

- [ ] **Step 4: Run focused tests and migration verification**

Run: `.venv/bin/python -m pytest tests/test_phase_6_author_studio.py -k persist -x -q && .venv/bin/python -m alembic upgrade head`

Expected: focused tests pass and Alembic exits 0.

- [ ] **Step 5: Commit the persistence slice**

```bash
git add backend/app/models backend/app/main.py backend/alembic/versions/0a1b2c3d4e5f_phase_6_author_studio.py backend/tests/test_phase_6_author_studio.py
git commit -m "feat: add author studio persistence"
```

## Task 2: Implement session repository, schemas, and ownership service

**Files:**
- Create: `backend/app/repositories/writing_session_repo.py`
- Create: `backend/app/schemas/writing_studio.py`
- Create: `backend/app/services/writing_session_service.py`
- Test: `backend/tests/test_phase_6_author_studio.py`

**Interfaces:**
- Consumes: models created in Task 1 and `WritingService.ensure_owned_novel()` ownership semantics.
- Produces: `WritingSessionService.create_session()`, `get_session()`, `list_sessions()`, `get_or_create_for_run()`, and Pydantic `WritingSessionOut` / `WritingMessageOut` / `StudioSourceOut`.

- [ ] **Step 1: Write failing service tests**

```python
@pytest.mark.asyncio
async def test_get_or_create_for_run_reuses_one_session(db):
    user, novel, completed_run, _ = await _make_studio_run(db)
    service = WritingSessionService(db, user.id, novel.id)
    first = await service.get_or_create_for_run(completed_run.id)
    second = await service.get_or_create_for_run(completed_run.id)
    assert second.id == first.id


@pytest.mark.asyncio
async def test_session_from_another_user_raises_not_found(db):
    _, novel, completed_run, _ = await _make_studio_run(db)
    other_user = User(username="studio_other", hashed_password="x")
    db.add(other_user)
    await db.flush()
    service = WritingSessionService(db, other_user.id, novel.id)
    with pytest.raises(NotFound):
        await service.get_or_create_for_run(completed_run.id)
```

- [ ] **Step 2: Run the service tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_phase_6_author_studio.py -k "create_for_run or another_user" -x -q`

Expected: FAIL because `WritingSessionService` does not exist.

- [ ] **Step 3: Implement repository, schemas, and service**

```python
class WritingSessionRepo:
    async def list_by_novel(self, novel_id: int) -> list[WritingSession]:
        result = await self.db.execute(
            select(WritingSession).where(WritingSession.novel_id == novel_id)
            .order_by(WritingSession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, session_id: int, novel_id: int) -> WritingSession | None:
        result = await self.db.execute(
            select(WritingSession).where(
                WritingSession.id == session_id, WritingSession.novel_id == novel_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_run(self, novel_id: int, run_id: int) -> WritingSession | None:
        result = await self.db.execute(
            select(WritingSession).where(
                WritingSession.novel_id == novel_id,
                WritingSession.active_writing_run_id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, novel_id: int, data: dict) -> WritingSession:
        session = WritingSession(novel_id=novel_id, **data)
        self.db.add(session)
        await self.db.flush()
        return session

    async def list_messages(self, session_id: int) -> list[WritingMessage]:
        result = await self.db.execute(
            select(WritingMessage).where(WritingMessage.session_id == session_id)
            .order_by(WritingMessage.created_at.asc(), WritingMessage.id.asc())
        )
        return list(result.scalars().all())

    async def get_by_idempotency_key(self, key: str) -> WritingMessage | None:
        result = await self.db.execute(
            select(WritingMessage).where(WritingMessage.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def upsert_working_copy(self, run_id: int, data: dict) -> DraftWorkingCopy:
        copy = await self.db.get(DraftWorkingCopy, run_id)
        if copy is None:
            copy = DraftWorkingCopy(writing_run_id=run_id, **data)
            self.db.add(copy)
        else:
            for key, value in data.items():
                setattr(copy, key, value)
        await self.db.flush()
        return copy

class WritingSessionService:
    async def create_session(self, target_chapter_id: int | None, title: str) -> WritingSession:
        await self._ensure_owned_novel()
        return await self.repo.create(self.novel_id, {
            "target_chapter_id": target_chapter_id, "title": title, "status": "active",
        })

    async def get_session(self, session_id: int) -> WritingSession:
        session = await self.repo.get(session_id, self.novel_id)
        if session is None:
            raise NotFound("创作会话不存在")
        return session

    async def list_sessions(self) -> list[WritingSession]:
        await self._ensure_owned_novel()
        return await self.repo.list_by_novel(self.novel_id)

    async def get_or_create_for_run(self, run_id: int) -> WritingSession:
        run = await self._get_owned_run(run_id)
        existing = await self.repo.get_by_run(self.novel_id, run.id)
        if existing is not None:
            return existing
        session = await self.repo.create(self.novel_id, {
            "target_chapter_id": run.target_chapter_id,
            "active_writing_run_id": run.id,
            "title": f"草稿 {run.id}", "status": "active",
        })
        run.writing_session_id = session.id
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def list_messages(self, session_id: int) -> list[WritingMessage]:
        await self.get_session(session_id)
        return await self.repo.list_messages(session_id)

    async def get_sources(self, run_id: int) -> list[StudioSourceOut]:
        run = await self._get_owned_run(run_id)
        items = run.context_snapshot_json.get("source_items", [])
        return [StudioSourceOut.model_validate(item) for item in items]
```

`get_sources()` reads only `WritingRun.context_snapshot_json.get("source_items", [])`, validates the run belongs to the session novel, and projects the six fields from the approved snapshot contract. It does not look up a newer ContextPackage.

Define the request and response models in the same task so that all route signatures in Task 5 exist before the router is written:

```python
class CreateWritingSessionRequest(BaseModel):
    title: str = Field(default="新创作会话", min_length=1, max_length=200)
    target_chapter_id: int | None = None

class StudioMessageCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    idempotency_key: str = Field(min_length=1, max_length=128)

class StudioActionRequest(BaseModel):
    action: Literal["accept", "discard", "apply_revision", "force_accept", "restore_version"]
    payload: dict = Field(default_factory=dict)

class WorkingCopySaveRequest(BaseModel):
    title: str = Field(max_length=500)
    content: str
    base_revision_sequence: int = Field(ge=0)

class StudioSourceOut(BaseModel):
    source_id: str
    source_type: str
    title: str
    locator: dict
    preview: str
    inclusion_reason: str

class WritingSessionOut(BaseModel):
    id: int
    novel_id: int
    target_chapter_id: int | None
    active_writing_run_id: int | None
    title: str
    status: str
    model_config = {"from_attributes": True}

class WritingMessageOut(BaseModel):
    id: int
    session_id: int
    role: Literal["author", "assistant", "system"]
    message_type: str
    content_json: dict
    action_status: Literal["running", "completed", "needs_confirmation", "failed"]
    writing_run_id: int | None
    context_package_id: int | None
    draft_version_id: int | None
    model_config = {"from_attributes": True}

class DraftWorkingCopyOut(BaseModel):
    writing_run_id: int
    draft_version_id: int
    title: str
    content: str
    base_revision_sequence: int
    model_config = {"from_attributes": True}

class StudioWorkspaceOut(BaseModel):
    session: WritingSessionOut
    messages: list[WritingMessageOut]
    working_copy: DraftWorkingCopyOut | None

class StudioMessageResult(BaseModel):
    assistant_message: WritingMessageOut
    workspace: StudioWorkspaceOut
```

Add the following private helpers and workspace serializer to `WritingSessionService`; they make every route and later service use the same ownership boundary:

```python
async def _ensure_owned_novel(self) -> Novel:
    novel = await self.db.get(Novel, self.novel_id)
    if novel is None or novel.user_id != self.user_id:
        raise NotFound("小说不存在")
    return novel

async def _get_owned_run(self, run_id: int) -> WritingRun:
    await self._ensure_owned_novel()
    run = await self.run_repo.get_by_id(run_id)
    if run is None or run.novel_id != self.novel_id:
        raise NotFound("写作运行不存在")
    return run

async def to_workspace_out(self, session: WritingSession) -> dict:
    messages = await self.repo.list_messages(session.id)
    working_copy = None
    if session.active_writing_run_id is not None:
        working_copy = await self.db.get(DraftWorkingCopy, session.active_writing_run_id)
    return {
        "session": WritingSessionOut.model_validate(session).model_dump(),
        "messages": [WritingMessageOut.model_validate(item).model_dump() for item in messages],
        "working_copy": DraftWorkingCopyOut.model_validate(working_copy).model_dump() if working_copy else None,
    }
```

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_phase_6_author_studio.py -k "create_for_run or another_user or sources" -x -q`

Expected: PASS.

- [ ] **Step 5: Commit the session lifecycle slice**

```bash
git add backend/app/repositories/writing_session_repo.py backend/app/schemas/writing_studio.py backend/app/services/writing_session_service.py backend/tests/test_phase_6_author_studio.py
git commit -m "feat: add writing session lifecycle"
```

## Task 3: Add WorkingCopy autosave and atomic revision flush

**Files:**
- Create: `backend/app/services/working_copy_service.py`
- Modify: `backend/app/services/draft_version_service.py`
- Modify: `backend/app/repositories/writing_session_repo.py`
- Test: `backend/tests/test_phase_6_author_studio.py`

**Interfaces:**
- Consumes: `DraftWorkingCopy`, `DraftVersionService.save_manual_revision()`, `DraftVersion.revision_sequence`.
- Produces: `WorkingCopyService.save(run_id, title, content, base_revision_sequence)` and `flush(run_id, reason="作者工作副本保存")`.

- [ ] **Step 1: Write failing WorkingCopy tests**

```python
@pytest.mark.asyncio
async def test_flush_turns_changed_working_copy_into_one_manual_revision(db):
    user, novel, completed_run, draft_version = await _make_studio_run(db)
    service = WorkingCopyService(db, user.id, novel.id)
    await service.save(completed_run.id, "雨夜账册", "作者改过的正文", 0)
    version = await service.flush(completed_run.id)
    assert version.content == "作者改过的正文"
    revisions = await DraftVersionRepo(db).list_revisions(version.id)
    assert [r.source_type for r in revisions] == ["manual_edit"]


@pytest.mark.asyncio
async def test_stale_working_copy_does_not_overwrite_new_revision(db):
    user, novel, completed_run, _ = await _make_studio_run(db)
    service = WorkingCopyService(db, user.id, novel.id)
    with pytest.raises(BadRequest, match="基础修订序列已过期"):
        await service.save(completed_run.id, "标题", "冲突正文", 99)
```

- [ ] **Step 2: Run the WorkingCopy tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_phase_6_author_studio.py -k "working_copy or stale" -x -q`

Expected: FAIL because `WorkingCopyService` does not exist.

- [ ] **Step 3: Implement save and flush behavior**

```python
class WorkingCopyService:
    async def save(self, run_id: int, title: str, content: str,
                   base_revision_sequence: int) -> DraftWorkingCopy:
        run = await self._get_owned_mutable_run(run_id)
        version = await self.version_repo.get_current(run.id)
        if version is None or version.revision_sequence != base_revision_sequence:
            raise BadRequest("基础修订序列已过期，请刷新后重试")
        return await self.repo.upsert_working_copy(run.id, {
            "draft_version_id": version.id, "title": title, "content": content,
            "base_revision_sequence": base_revision_sequence,
        })

    async def flush(self, run_id: int, reason: str = "作者工作副本保存") -> DraftVersion:
        copy = await self._get_owned_copy(run_id)
        version = await self.version_repo.get_current(run_id)
        if copy.content == version.content:
            return version
        version, _ = await self.version_service.save_manual_revision(
            run_id, copy.content, reason, copy.base_revision_sequence,
        )
        copy.draft_version_id = version.id
        copy.base_revision_sequence = version.revision_sequence
        await self.db.commit()
        return version
```

Initialize a WorkingCopy at the same transaction boundary as `ensure_initial_version()` after a completed run is first opened in Studio. Before Studio action handlers accept a run, create a revision, request a revision, apply a revision, or restore a version, invoke `flush()`.

- [ ] **Step 4: Run WorkingCopy and existing version tests**

Run: `.venv/bin/python -m pytest tests/test_phase_6_author_studio.py -k "working_copy or stale" -x -q && .venv/bin/python -m pytest tests/test_phase_4_draft_versions.py -x -q`

Expected: both commands pass.

- [ ] **Step 5: Commit the WorkingCopy slice**

```bash
git add backend/app/services/working_copy_service.py backend/app/services/draft_version_service.py backend/app/repositories/writing_session_repo.py backend/tests/test_phase_6_author_studio.py
git commit -m "feat: persist studio working copies"
```

## Task 4: Implement restricted StudioAgent and message orchestration

**Files:**
- Create: `backend/app/ai/studio_agent.py`
- Create: `backend/app/services/writing_studio_service.py`
- Modify: `backend/app/schemas/writing_studio.py`
- Test: `backend/tests/test_phase_6_author_studio.py`

**Interfaces:**
- Consumes: `WritingSessionService`, `WorkingCopyService`, `WritingService`, `DraftVersionService`, and existing review/modification services.
- Produces: `StudioIntentAgent.interpret()`, `StudioActionExecutor.execute()`, `WritingStudioService.send_author_message()`, and `WritingStudioService.confirm_action()`.

- [ ] **Step 1: Write failing orchestration tests with a fake intent agent**

```python
class FakeStudioIntentAgent:
    async def interpret(self, text: str, session: WritingSession) -> StudioIntent:
        return StudioIntent(action="generate_draft", reply="开始生成草稿", payload={})

class FakeAcceptIntentAgent:
    async def interpret(self, text: str, session: WritingSession) -> StudioIntent:
        return StudioIntent(action="clarify", reply="请确认接受草稿", payload={}, confirmation_action="accept")

class FakeStudioActionExecutor:
    async def execute(self, session: WritingSession, intent: StudioIntent) -> StudioActionResult:
        return StudioActionResult(
            message_type="draft", content_json={"summary": "草稿已生成"},
            writing_run_id=session.active_writing_run_id, context_package_id=None, draft_version_id=None,
        )

@pytest.mark.asyncio
async def test_send_message_is_idempotent_and_links_completed_run(db):
    user, novel, run, _ = await _make_studio_run(db)
    session = await WritingSessionService(db, user.id, novel.id).get_or_create_for_run(run.id)
    service = WritingStudioService(db, user.id, novel.id, intent_agent=FakeStudioIntentAgent(),
                                   action_executor=FakeStudioActionExecutor())
    result = await service.send_author_message(session.id, "写下一章", "request-001")
    replay = await service.send_author_message(session.id, "写下一章", "request-001")
    assert replay.assistant_message.id == result.assistant_message.id
    assert result.assistant_message.writing_run_id is not None

@pytest.mark.asyncio
async def test_accept_request_requires_confirm_action_not_text(db):
    user, novel, run, _ = await _make_studio_run(db)
    session = await WritingSessionService(db, user.id, novel.id).get_or_create_for_run(run.id)
    service = WritingStudioService(db, user.id, novel.id, intent_agent=FakeAcceptIntentAgent(),
                                   action_executor=FakeStudioActionExecutor())
    result = await service.send_author_message(session.id, "接受这个草稿", "request-002")
    assert result.assistant_message.action_status == "needs_confirmation"
```

- [ ] **Step 2: Run orchestration tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_phase_6_author_studio.py -k "idempotent or requires_confirm" -x -q`

Expected: FAIL because `StudioIntentAgent` and `WritingStudioService` do not exist.

- [ ] **Step 3: Implement a restricted intent protocol and coordinator**

```python
StudioAction = Literal[
    "clarify", "generate_plan", "generate_brief", "generate_context",
    "generate_draft", "review_draft", "propose_revision", "explain_sources",
]

class StudioIntent(BaseModel):
    action: StudioAction
    reply: str
    payload: dict = Field(default_factory=dict)
    confirmation_action: Literal["accept", "discard", "apply_revision", "force_accept", "restore_version"] | None = None

class StudioActionResult(BaseModel):
    message_type: str
    content_json: dict
    writing_run_id: int | None = None
    context_package_id: int | None = None
    draft_version_id: int | None = None

class StudioIntentAgent(Protocol):
    async def interpret(self, text: str, session: WritingSession) -> StudioIntent:
        raise NotImplementedError

class StudioActionExecutor(Protocol):
    async def execute(self, session: WritingSession, intent: StudioIntent) -> StudioActionResult:
        raise NotImplementedError

class WritingStudioService:
    async def send_author_message(self, session_id: int, text: str,
                                  idempotency_key: str) -> StudioMessageResult:
        existing = await self.session_repo.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return await self._result_for_existing_message(existing)
        session = await self.session_service.get_session(session_id)
        author, assistant = await self._create_message_pair(session, text, idempotency_key)
        intent = await self.intent_agent.interpret(text, session)
        if intent.confirmation_action is not None:
            assistant.message_type = "action"
            assistant.content_json = {"reply": intent.reply, "action": intent.confirmation_action}
            assistant.action_status = "needs_confirmation"
            await self.db.commit()
            return await self._result_for_existing_message(assistant)
        return await self._dispatch_intent(session, author, assistant, intent)

    async def confirm_action(self, session_id: int, message_id: int,
                             action: Literal["accept", "discard", "apply_revision", "force_accept", "restore_version"],
                             payload: dict) -> StudioMessageResult:
        message = await self._get_confirmable_message(session_id, message_id, action)
        await self.working_copy_service.flush(message.writing_run_id)
        return await self._dispatch_confirmation(message, action, payload)
```

`send_author_message()` first returns the existing message result when its idempotency key already exists. Otherwise it inserts the author message and a `running` assistant message in one transaction, calls the restricted agent, and delegates each permitted action to the existing owning service. It saves `writing_run_id`, `context_package_id`, and `draft_version_id` on the assistant message returned by those services. For confirmation-only verbs it writes `action_status="needs_confirmation"` and stores an action-card payload; it does not call acceptance or discard services.

The production `DeepSeekStudioIntentAgent` uses the existing AI configuration and validates its JSON output through `StudioIntent`; malformed output becomes a `clarify` response, not an unvalidated mutation.

- [ ] **Step 4: Run orchestration tests**

Run: `.venv/bin/python -m pytest tests/test_phase_6_author_studio.py -k "idempotent or requires_confirm or malformed" -x -q`

Expected: PASS.

- [ ] **Step 5: Commit the orchestration slice**

```bash
git add backend/app/ai/studio_agent.py backend/app/services/writing_studio_service.py backend/app/schemas/writing_studio.py backend/tests/test_phase_6_author_studio.py
git commit -m "feat: orchestrate studio conversations"
```

## Task 5: Expose Studio REST endpoints and source snapshots

**Files:**
- Create: `backend/app/api/writing_studio.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas/writing_studio.py`
- Test: `backend/tests/test_phase_6_author_studio.py`

**Interfaces:**
- Consumes: services from Tasks 2–4.
- Produces: seven nested Studio endpoints and `GET /writing-runs/{run_id}/sources`.

- [ ] **Step 1: Write failing API tests using authenticated AsyncClient**

```python
@pytest.mark.asyncio
async def test_session_api_restores_messages_working_copy_and_sources(client, db):
    user, novel, completed_run, _ = await _make_studio_run(db)
    await db.commit()
    headers = {"Authorization": f"Bearer {create_token({'user_id': user.id})}"}
    created = await client.post(f"/api/v1/novels/{novel.id}/writing-sessions",
                                headers=headers, json={"title": "第十八章"})
    session_id = created.json()["data"]["id"]
    message = await client.post(
        f"/api/v1/novels/{novel.id}/writing-sessions/{session_id}/messages",
        headers=headers, json={"text": "解释本次来源", "idempotency_key": "api-001"},
    )
    restored = await client.get(f"/api/v1/novels/{novel.id}/writing-sessions/{session_id}", headers=headers)
    sources = await client.get(f"/api/v1/novels/{novel.id}/writing-runs/{completed_run.id}/sources", headers=headers)
    assert message.json()["code"] == 0
    assert restored.json()["data"]["messages"]
    assert sources.json()["data"] == completed_run.context_snapshot_json["source_items"]
```

- [ ] **Step 2: Run API tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_phase_6_author_studio.py -k "session_api" -x -q`

Expected: FAIL with 404 because the Studio router is not registered.

- [ ] **Step 3: Implement router and dependency wiring**

```python
router = APIRouter(prefix="/novels/{novel_id}", tags=["Writing Studio"])

@router.post("/writing-sessions")
async def create_session(
    novel_id: int, body: CreateWritingSessionRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    session = await WritingSessionService(db, current_user.id, novel_id).create_session(
        body.target_chapter_id, body.title,
    )
    return ApiResponse.success(data=WritingSessionOut.model_validate(session).model_dump())

@router.get("/writing-sessions")
async def list_sessions(
    novel_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    sessions = await WritingSessionService(db, current_user.id, novel_id).list_sessions()
    return ApiResponse.success(data=[WritingSessionOut.model_validate(item).model_dump() for item in sessions])

@router.get("/writing-sessions/{session_id}")
async def get_session(
    novel_id: int, session_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    service = WritingSessionService(db, current_user.id, novel_id)
    session = await service.get_session(session_id)
    return ApiResponse.success(data=await service.to_workspace_out(session))

@router.post("/writing-sessions/{session_id}/messages")
async def send_message(
    novel_id: int, session_id: int, body: StudioMessageCreateRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    result = await WritingStudioService(db, current_user.id, novel_id).send_author_message(
        session_id, body.text, body.idempotency_key,
    )
    return ApiResponse.success(data=result.model_dump())

@router.post("/writing-sessions/{session_id}/actions/{message_id}")
async def confirm_action(
    novel_id: int, session_id: int, message_id: int, body: StudioActionRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    result = await WritingStudioService(db, current_user.id, novel_id).confirm_action(
        session_id, message_id, body.action, body.payload,
    )
    return ApiResponse.success(data=result.model_dump())

@router.put("/writing-sessions/{session_id}/working-copy")
async def save_working_copy(
    novel_id: int, session_id: int, body: WorkingCopySaveRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    session = await WritingSessionService(db, current_user.id, novel_id).get_session(session_id)
    if session.active_writing_run_id is None:
        raise BadRequest("当前会话没有可保存的草稿")
    copy = await WorkingCopyService(db, current_user.id, novel_id).save(
        session.active_writing_run_id, body.title, body.content, body.base_revision_sequence,
    )
    return ApiResponse.success(data=DraftWorkingCopyOut.model_validate(copy).model_dump())

@router.get("/writing-runs/{run_id}/sources")
async def get_run_sources(
    novel_id: int, run_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    sources = await WritingSessionService(db, current_user.id, novel_id).get_sources(run_id)
    return ApiResponse.success(data=[item.model_dump() for item in sources])
```

Every endpoint obtains the authenticated user through `get_current_user`, creates the service with the route `novel_id`, and serializes only Pydantic output models. Include `writing_studio.router` in `create_app()` under `/api/v1`.

- [ ] **Step 4: Run Studio API and existing API regression tests**

Run: `.venv/bin/python -m pytest tests/test_phase_6_author_studio.py -k "session_api or source" -x -q && .venv/bin/python -m pytest tests/test_phase_4_api.py -x -q`

Expected: both commands pass.

- [ ] **Step 5: Commit the API slice**

```bash
git add backend/app/api/writing_studio.py backend/app/main.py backend/app/schemas/writing_studio.py backend/tests/test_phase_6_author_studio.py
git commit -m "feat: expose studio session api"
```

## Task 6: Add frontend Studio contracts, API client, and Pinia store

**Files:**
- Create: `frontend/src/types/writingStudio.ts`
- Create: `frontend/src/api/writingStudio.ts`
- Create: `frontend/src/stores/writingStudio.ts`
- Create: `frontend/src/__tests__/WritingStudioStore.spec.ts`

**Interfaces:**
- Consumes: Task 5 API response contracts.
- Produces: `useWritingStudioStore` with `loadSession`, `selectDocument`, `sendMessage`, `confirmAction`, and `saveWorkingCopy`.

- [ ] **Step 1: Write failing Pinia store tests**

```ts
it('keeps a pending author message and replaces it with the server session result', async () => {
  vi.mocked(api.sendStudioMessage).mockResolvedValue(sessionFixture)
  const store = useWritingStudioStore()
  store.session = sessionFixture

  await store.sendMessage(1, '让结尾更克制')

  expect(api.sendStudioMessage).toHaveBeenCalledWith(1, 7, expect.objectContaining({ text: '让结尾更克制' }))
  expect(store.messages.at(-1)?.role).toBe('assistant')
})

it('does not replace local document text when working-copy save fails', async () => {
  vi.mocked(api.saveWorkingCopy).mockRejectedValue(new Error('network'))
  const store = useWritingStudioStore()
  store.document = { kind: 'draft', content: '作者正文', title: '第十八章', baseRevisionSequence: 0 }
  await expect(store.saveWorkingCopy(1)).rejects.toThrow('network')
  expect(store.document?.content).toBe('作者正文')
})
```

- [ ] **Step 2: Run the store test to verify it fails**

Run: `npm run test:unit -- --run src/__tests__/WritingStudioStore.spec.ts`

Expected: FAIL because the Studio API module and store do not exist.

- [ ] **Step 3: Implement TypeScript contracts, API methods, and store state**

```ts
export type StudioMessageRole = 'author' | 'assistant' | 'system'
export type StudioActionStatus = 'running' | 'completed' | 'needs_confirmation' | 'failed'
export type StudioConfirmationAction = 'accept' | 'discard' | 'apply_revision' | 'force_accept' | 'restore_version'

export interface WritingSession {
  id: number
  novel_id: number
  target_chapter_id: number | null
  active_writing_run_id: number | null
  title: string
  status: string
}

export interface WritingMessage {
  id: number
  session_id: number
  role: StudioMessageRole
  message_type: string
  content_json: Record<string, unknown>
  action_status: StudioActionStatus
  writing_run_id: number | null
  context_package_id: number | null
  draft_version_id: number | null
}

export interface DraftWorkingCopy {
  writing_run_id: number
  draft_version_id: number
  title: string
  content: string
  base_revision_sequence: number
}

export interface StudioDocument {
  kind: 'chapter' | 'draft'
  chapterId?: number
  writingRunId?: number
  draftVersionId?: number
  title: string
  content: string
  baseRevisionSequence: number
}

export interface StudioWorkspace {
  session: WritingSession
  messages: WritingMessage[]
  working_copy: DraftWorkingCopy | null
}

export interface StudioMessageResult {
  assistant_message: WritingMessage
  workspace: StudioWorkspace
}

export const useWritingStudioStore = defineStore('writingStudio', () => {
  const session = ref<WritingSession | null>(null)
  const messages = ref<WritingMessage[]>([])
  const document = ref<StudioDocument | null>(null)
  const saveState = ref<'idle' | 'saving' | 'saved' | 'conflict' | 'error'>('idle')
  function hydrate(workspace: StudioWorkspace): void {
    session.value = workspace.session
    messages.value = workspace.messages
    document.value = workspace.working_copy ? {
        kind: 'draft', writingRunId: workspace.working_copy.writing_run_id,
        draftVersionId: workspace.working_copy.draft_version_id,
        title: workspace.working_copy.title, content: workspace.working_copy.content,
        baseRevisionSequence: workspace.working_copy.base_revision_sequence,
      } : null
  }
  async function loadSession(novelId: number, sessionId: number): Promise<void> {
    hydrate(await api.getStudioSession(novelId, sessionId))
  }
  async function sendMessage(novelId: number, text: string): Promise<void> {
    if (!session.value) throw new Error('请先选择创作会话')
    const result = await api.sendStudioMessage(novelId, session.value.id, {
      text, idempotency_key: crypto.randomUUID(),
    })
    hydrate(result.workspace)
  }
  async function confirmAction(novelId: number, messageId: number,
                               action: StudioConfirmationAction, payload: Record<string, unknown> = {}): Promise<void> {
    if (!session.value) throw new Error('请先选择创作会话')
    const result = await api.confirmStudioAction(novelId, session.value.id, messageId, { action, payload })
    hydrate(result.workspace)
  }
  async function saveWorkingCopy(novelId: number): Promise<void> {
    if (!session.value || !document.value || document.value.kind !== 'draft') return
    saveState.value = 'saving'
    try {
      const copy = await api.saveStudioWorkingCopy(novelId, session.value.id, {
        title: document.value.title, content: document.value.content,
        base_revision_sequence: document.value.baseRevisionSequence,
      })
      document.value.baseRevisionSequence = copy.base_revision_sequence
      saveState.value = 'saved'
    } catch (error) {
      saveState.value = error instanceof Error && error.message.includes('基础修订序列已过期') ? 'conflict' : 'error'
      throw error
    }
  }
  return { session, messages, document, saveState, loadSession, sendMessage, confirmAction, saveWorkingCopy }
})
```

Define the matching API functions in `api/writingStudio.ts`; each returns the unwrapped response from the existing Axios client:

```ts
export function getStudioSession(novelId: number, sessionId: number): Promise<StudioWorkspace> {
  return client.get(`/novels/${novelId}/writing-sessions/${sessionId}`)
}
export function sendStudioMessage(novelId: number, sessionId: number, body: { text: string; idempotency_key: string }): Promise<StudioMessageResult> {
  return client.post(`/novels/${novelId}/writing-sessions/${sessionId}/messages`, body)
}
export function confirmStudioAction(novelId: number, sessionId: number, messageId: number,
                                    body: { action: StudioConfirmationAction; payload: Record<string, unknown> }): Promise<StudioMessageResult> {
  return client.post(`/novels/${novelId}/writing-sessions/${sessionId}/actions/${messageId}`, body)
}
export function saveStudioWorkingCopy(novelId: number, sessionId: number,
                                      body: { title: string; content: string; base_revision_sequence: number }): Promise<DraftWorkingCopy> {
  return client.put(`/novels/${novelId}/writing-sessions/${sessionId}/working-copy`, body)
}
```

Generate request IDs with `crypto.randomUUID()` and retain them on retries so UI retries reuse server idempotency behavior.

- [ ] **Step 4: Run the store test and type check**

Run: `npm run test:unit -- --run src/__tests__/WritingStudioStore.spec.ts && npm run type-check`

Expected: both commands pass.

- [ ] **Step 5: Commit the frontend data slice**

```bash
git add frontend/src/types/writingStudio.ts frontend/src/api/writingStudio.ts frontend/src/stores/writingStudio.ts frontend/src/__tests__/WritingStudioStore.spec.ts
git commit -m "feat: add studio frontend state"
```

## Task 7: Build the full-screen route and left chapter/draft explorer

**Files:**
- Create: `frontend/src/views/studio/StudioView.vue`
- Create: `frontend/src/components/studio/StudioChapterExplorer.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/novels/NovelWorkspaceTabs.vue`
- Modify: `frontend/src/views/novels/NovelDetailView.vue`
- Create: `frontend/src/__tests__/StudioView.spec.ts`

**Interfaces:**
- Consumes: `useNovelStore`, `useWritingStudioStore`, and Studio routes.
- Produces: `studio` route outside `AppLayout`, Explorer `select` events with `{ kind, chapterId?, sessionId? }`.

- [ ] **Step 1: Write failing route and explorer tests**

```ts
it('opens the Studio full-screen route without AppLayout and groups unaccepted runs as 草稿', async () => {
  router.push('/novels/1/studio?session_id=7')
  await router.isReady()
  const wrapper = mount(StudioView, { global: { plugins: [router, createPinia()] } })
  expect(wrapper.find('[data-testid="studio-workbench"]').exists()).toBe(true)
  expect(wrapper.get('[data-testid="studio-drafts-group"]').text()).toContain('草稿')
})

it('redirects the legacy editor route to the selected Studio chapter', async () => {
  await router.push('/novels/1/edit/18')
  expect(router.currentRoute.value.fullPath).toBe('/novels/1/studio?chapter_id=18')
})
```

- [ ] **Step 2: Run route and explorer tests to verify they fail**

Run: `npm run test:unit -- --run src/__tests__/StudioView.spec.ts`

Expected: FAIL because StudioView and the route do not exist.

- [ ] **Step 3: Implement layout, explorer, and route migration**

```ts
// router/index.ts, outside the AppLayout route tree
{ path: '/novels/:id/studio', name: 'studio', component: () => import('@/views/studio/StudioView.vue'), meta: { auth: true } },
{ path: '/novels/:id/edit/:chapterId', redirect: to => ({ name: 'studio', query: { chapter_id: String(to.params.chapterId) } }) },
// replace the AppLayout child writing route with a redirect to { name: 'studio' }
```

`StudioView` uses CSS grid `grid-template-columns: 240px minmax(640px, 1fr) 380px; min-height: 100vh`. At `max-width: 1279px` it exposes a left-pane toggle; at `max-width: 1023px` both side panes become Element Plus drawers. `StudioChapterExplorer` lists accepted chapters from `novelStore.currentNovel.chapters` and unaccepted runs/session summaries from `writingStudioStore` in separate `data-testid="studio-chapters-group"` and `data-testid="studio-drafts-group"` groups.

- [ ] **Step 4: Run Studio route tests**

Run: `npm run test:unit -- --run src/__tests__/StudioView.spec.ts && npm run type-check`

Expected: both commands pass.

- [ ] **Step 5: Commit the Studio shell**

```bash
git add frontend/src/views/studio/StudioView.vue frontend/src/components/studio/StudioChapterExplorer.vue frontend/src/router/index.ts frontend/src/components/novels/NovelWorkspaceTabs.vue frontend/src/views/novels/NovelDetailView.vue frontend/src/__tests__/StudioView.spec.ts
git commit -m "feat: add full-screen author studio"
```

## Task 8: Implement the central document pane and autosave UX

**Files:**
- Create: `frontend/src/components/studio/StudioDocumentPane.vue`
- Create: `frontend/src/components/studio/StudioVersionInspector.vue`
- Modify: `frontend/src/views/studio/StudioView.vue`
- Modify: `frontend/src/stores/writingStudio.ts`
- Modify: `frontend/src/__tests__/StudioView.spec.ts`

**Interfaces:**
- Consumes: `StudioDocument`, `saveState`, `saveWorkingCopy()`, existing `DraftVersionTimeline`, and existing revision API/store.
- Produces: an editor that emits `update:title`, `update:content`, `accept`, `discard`, and `open-version-inspector`.

- [ ] **Step 1: Write failing autosave and safety tests**

```ts
it('debounces draft edits into one WorkingCopy save and reports 已保存', async () => {
  vi.useFakeTimers()
  const wrapper = mount(StudioDocumentPane, { props: { document: draftDocument, saveState: 'idle' } })
  await wrapper.get('[data-testid="studio-document-content"]').setValue('新的正文')
  await vi.advanceTimersByTimeAsync(800)
  expect(wrapper.emitted('save-working-copy')?.[0]).toEqual(['新的正文', draftDocument.baseRevisionSequence])
})

it('keeps the author buffer after a save error', async () => {
  const failedDocument = Object.assign({}, draftDocument, { content: '作者文字' })
  const wrapper = mount(StudioDocumentPane, { props: { document: failedDocument, saveState: 'error' } })
  expect(wrapper.get('[data-testid="studio-document-content"]').element.value).toBe('作者文字')
})
```

- [ ] **Step 2: Run document-pane tests to verify they fail**

Run: `npm run test:unit -- --run src/__tests__/StudioView.spec.ts`

Expected: FAIL because StudioDocumentPane does not exist.

- [ ] **Step 3: Implement document pane and version inspector**

Use the existing serif text treatment from `components/editor/WritingEditor.vue`, but make `StudioDocumentPane` a focused controlled component. For draft documents, debounce `save-working-copy` by 800ms; for accepted chapters, delegate the existing `novelStore.updateChapter()` save path. Render a persistent top status with exact labels `保存中…`, `已保存`, `保存失败`, and `版本冲突`.

```ts
watch(() => props.document, value => {
  title.value = value?.title ?? ''
  content.value = value?.content ?? ''
}, { immediate: true, deep: true })

function scheduleDraftSave() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => emit('save-working-copy', {
    title: title.value,
    content: content.value,
    baseRevisionSequence: props.document.baseRevisionSequence,
  }), 800)
}
```

`StudioVersionInspector` wraps existing `DraftVersionTimeline`, `RevisionHistoryPanel`, `ReviewIssuePanel`, and `RevisionCandidatePanel` in an `el-drawer`; it never renders these panels inline in the middle document column.

- [ ] **Step 4: Run document and existing editor tests**

Run: `npm run test:unit -- --run src/__tests__/StudioView.spec.ts src/__tests__/WritingEditor.spec.ts && npm run type-check`

Expected: all tests and type checking pass.

- [ ] **Step 5: Commit the editor slice**

```bash
git add frontend/src/components/studio/StudioDocumentPane.vue frontend/src/components/studio/StudioVersionInspector.vue frontend/src/views/studio/StudioView.vue frontend/src/stores/writingStudio.ts frontend/src/__tests__/StudioView.spec.ts
git commit -m "feat: add studio document autosave"
```

## Task 9: Implement conversation messages, confirmation cards, and sources panel

**Files:**
- Create: `frontend/src/components/studio/StudioConversationPane.vue`
- Create: `frontend/src/components/studio/StudioMessage.vue`
- Create: `frontend/src/components/studio/StudioActionCard.vue`
- Create: `frontend/src/components/studio/StudioSourcesPanel.vue`
- Modify: `frontend/src/views/studio/StudioView.vue`
- Modify: `frontend/src/__tests__/StudioView.spec.ts`

**Interfaces:**
- Consumes: Studio store messages and `StudioSource` snapshots.
- Produces: `send-message`, `confirm-action`, `open-sources`, and `retry-message` events.

- [ ] **Step 1: Write failing message and provenance tests**

```ts
it('renders sources only beneath the linked assistant message', async () => {
  const wrapper = mount(StudioConversationPane, { props: { messages: [assistantDraftMessage, authorMessage] } })
  await wrapper.get('[data-testid="studio-sources-trigger-21"]').trigger('click')
  expect(wrapper.get('[data-testid="studio-sources-panel-21"]').text()).toContain('第 18 章 · 第 3 场')
  expect(wrapper.text()).not.toContain('0.87')
})

it('does not emit accept until the author clicks the confirmation button', async () => {
  const wrapper = mount(StudioActionCard, { props: { message: acceptanceMessage } })
  expect(wrapper.emitted('confirm-action')).toBeUndefined()
  await wrapper.get('[data-testid="studio-confirm-accept"]').trigger('click')
  expect(wrapper.emitted('confirm-action')?.[0]).toEqual([acceptanceMessage.id, 'accept', {}])
})
```

- [ ] **Step 2: Run conversation tests to verify they fail**

Run: `npm run test:unit -- --run src/__tests__/StudioView.spec.ts`

Expected: FAIL because the conversation components do not exist.

- [ ] **Step 3: Implement the right-pane message system**

`StudioMessage` switches only on the backend `message_type` value: `text`, `plan`, `brief`, `context`, `draft`, `review`, `revision`, `sources`, `decision`, and `error`. `StudioActionCard` renders confirmation buttons solely for messages with `action_status === 'needs_confirmation'`; a `running` message shows a spinner and disables its retry control. `StudioSourcesPanel` calls `getRunSources()` on first expansion, caches sources by `writing_run_id`, and renders `title`, `preview`, and `inclusion_reason` only. Diagnostics are hidden behind an `el-collapse` section labelled `检索诊断`.

```ts
async function submit() {
  const text = composer.value.trim()
  if (!text || props.sending) return
  emit('send-message', text)
  composer.value = ''
}

function confirm(messageId: number, action: StudioConfirmationAction) {
  emit('confirm-action', messageId, action, {})
}
```

When a completed draft message references a run, `StudioView` selects its draft document only if the message belongs to the selected session. A message for another session never replaces the visible document.

- [ ] **Step 4: Run conversation and store tests**

Run: `npm run test:unit -- --run src/__tests__/StudioView.spec.ts src/__tests__/WritingStudioStore.spec.ts && npm run type-check`

Expected: all commands pass.

- [ ] **Step 5: Commit the collaboration pane slice**

```bash
git add frontend/src/components/studio/StudioConversationPane.vue frontend/src/components/studio/StudioMessage.vue frontend/src/components/studio/StudioActionCard.vue frontend/src/components/studio/StudioSourcesPanel.vue frontend/src/views/studio/StudioView.vue frontend/src/__tests__/StudioView.spec.ts
git commit -m "feat: add studio conversation sources"
```

## Task 10: Finish cutover, migration compatibility, and end-to-end verification

**Files:**
- Modify: `frontend/src/views/novels/WritingWorkspaceView.vue`
- Modify: `frontend/src/views/editor/EditorView.vue`
- Modify: `frontend/src/__tests__/WritingWorkspacePhase3.spec.ts`
- Modify: `frontend/src/__tests__/WritingWorkspacePhase4.spec.ts`
- Create: `frontend/e2e/studio.spec.ts`
- Modify: `backend/tests/test_phase_6_author_studio.py`

**Interfaces:**
- Consumes: every endpoint and component from Tasks 1–9.
- Produces: legacy links that enter Studio, comprehensive verification evidence, and no remaining production dependency on the vertical workflow view.

- [ ] **Step 1: Write failing migration and E2E tests**

```ts
const workspaceFixture = {
  code: 0,
  message: 'ok',
  data: {
    session: { id: 7, novel_id: 1, target_chapter_id: 18, active_writing_run_id: 21, title: '第十八章', status: 'active' },
    messages: [],
    working_copy: { writing_run_id: 21, draft_version_id: 31, title: '第十八章', content: '雨夜正文', base_revision_sequence: 0 },
  },
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('token', 'studio-e2e-token'))
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/writing-sessions/7')) {
      await route.fulfill({ json: workspaceFixture })
      return
    }
    if (url.pathname.endsWith('/novels/1')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: { id: 1, title: '测试小说', chapters: [] } } })
      return
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data: [] } })
  })
})

test('legacy writing link enters Studio and preserves a selected chapter', async ({ page }) => {
  await page.goto('/novels/1/edit/18')
  await expect(page).toHaveURL(/\/novels\/1\/studio\?chapter_id=18/)
  await expect(page.getByTestId('studio-workbench')).toBeVisible()
})

test('narrow Studio opens the AI pane as a drawer', async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 900 })
  await page.goto('/novels/1/studio?session_id=7')
  await page.getByRole('button', { name: '打开 AI 协作' }).click()
  await expect(page.getByTestId('studio-ai-drawer')).toBeVisible()
})
```

- [ ] **Step 2: Run the new E2E test to verify it fails**

Run: `npm run test:e2e -- studio.spec.ts`

Expected: FAIL until Studio routing, fixtures, and drawer behavior are all present.

- [ ] **Step 3: Complete legacy cutover and compatibility checks**

Replace `WritingWorkspaceView` and `EditorView` production bodies with compatibility redirects or remove their route use entirely after moving every direct link to Studio. Preserve their isolated component tests only where the tested component is still reused; replace vertical-workflow view tests with Studio behavior tests. Add a backend test that opens a pre-Phase-6 WritingRun with `writing_session_id is None` and proves Studio creates exactly one session while retaining the run and DraftVersion IDs.

- [ ] **Step 4: Run full backend verification**

Run: `.venv/bin/python -m pytest tests/ -x -q && .venv/bin/python -m alembic upgrade head`

Expected: all backend tests pass and migration exits 0.

- [ ] **Step 5: Run full frontend verification**

Run: `npm run test:unit && npm run type-check && npm run lint && npm run build && npm run test:e2e -- studio.spec.ts`

Expected: every command exits 0. If Playwright browsers are absent, install them with `npx playwright install` and rerun the E2E command.

- [ ] **Step 6: Commit the cutover and verification slice**

```bash
git add frontend/src/views frontend/src/router/index.ts frontend/src/__tests__ frontend/e2e/studio.spec.ts backend/tests/test_phase_6_author_studio.py
git commit -m "feat: complete author studio cutover"
```

## Plan Self-Review

### Spec coverage

| Approved requirement | Implementing tasks |
| --- | --- |
| Independent full-screen three-pane Studio | Tasks 7, 8, 9, 10 |
| Left chapters and unaccepted drafts | Tasks 2, 5, 7 |
| Central author-first document and automatic working-copy save | Tasks 3, 6, 8 |
| Persistent natural-language AI session | Tasks 1, 2, 4, 5, 6, 9 |
| Restricted AI mutations and confirmation cards | Tasks 4, 5, 9 |
| Source provenance tied to immutable WritingRun snapshot | Tasks 2, 5, 9 |
| Refresh recovery, idempotency, conflict, error safety | Tasks 2, 3, 4, 5, 6, 8, 10 |
| Compatibility with old routes and existing revision domain | Tasks 3, 7, 8, 10 |
| Desktop-first responsive behavior and verification | Tasks 7, 10 |

### Scope boundary

The plan deliberately stops at the canonical source snapshot boundary. A separate Phase 6 retrieval plan must install Qdrant, configure Model Studio embedding and rerank clients, index chapters/memories, and populate `source_items`/`diagnostics`; its only required Studio-facing contract is the snapshot shape in the approved design spec. This prevents an infrastructure rollout from blocking the author-workbench migration.

### Type consistency

- `WritingSession`, `WritingMessage`, and `DraftWorkingCopy` are defined in Task 1 and consumed by every later backend task.
- `WritingSessionService` methods are defined in Task 2 and used by `WritingStudioService` in Task 4.
- `WorkingCopyService.flush()` is defined in Task 3 and required before every Studio domain mutation in Task 4.
- `StudioDocument`, `StudioActionStatus`, and `useWritingStudioStore` are defined in Task 6 and consumed by Tasks 7–9.
- `StudioConfirmationAction` is the frontend mirror of the server confirmation-only action set; it excludes every direct AI action.
