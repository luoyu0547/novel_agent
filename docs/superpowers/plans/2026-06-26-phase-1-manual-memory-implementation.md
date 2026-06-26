# Phase 1 Manual Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the phase 1 manual memory loop by adding novel metadata, chapter summary/status, character cards, world settings, and the matching frontend management UI.

**Architecture:** Keep the current FastAPI layered backend (`api -> service -> repository -> model`) and Vue 3 frontend (`types -> api -> store -> views`). Backend owns validation, authorization, and persistence; frontend owns form state, route-level workflows, and display. This is one plan because the backend contract and frontend UI form one testable product slice.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, SQLite/MySQL-compatible schema, pytest, httpx, Vue 3, TypeScript, Pinia, Vue Router, SCSS, Vitest, Playwright.

## Global Constraints

- Scope: phase 1 only, no AI automatic extraction, no multi-agent orchestration, no RAG, no consistency checker.
- `Novel` adds `genre` and `style_guide`.
- `Chapter` adds `summary` and `status`.
- `Chapter.status` values are exactly `draft`, `reviewed`, and `locked`; backend default is `draft`.
- `locked` is status-only in this phase and does not block editing.
- `CharacterProfile` uses `story_role` for narrative function and `identity` for in-world identity.
- `speech_style` stores dialogue constraints, not just catchphrases.
- `behavior_rules` is a string array persisted as JSON.
- `WorldSetting.category` values are exactly `geography`, `faction`, `rule`, `history`, `culture`, and `other`.
- World setting category validation belongs in schema/service code, not a database enum.
- All child resources must verify the parent novel belongs to the current user.
- Keep existing unified API response format: `{"code": int, "message": str, "data": any}`.
- Do not modify the existing initial Alembic migration; create a new migration.
- Frontend routes for phase 1 memory are `/novels/:id/characters` and `/novels/:id/settings`.
- Character and setting edit flows use existing `AppModal`; destructive actions use existing `AppConfirm`.
- Chapter `summary` is edited below the chapter body.
- Frontend verification commands are `npm run type-check` and `npm run build`.

---

## File Structure

### Backend

- Modify: `backend/requirements.txt` — add backend test dependencies.
- Create: `backend/pytest.ini` — configure pytest async mode and import path.
- Create: `backend/tests/conftest.py` — isolated async SQLite test client and database reset.
- Create: `backend/tests/test_phase_1_manual_memory.py` — API tests for novel/chapter metadata and memory resources.
- Modify: `backend/app/models/novel.py` — add novel metadata and chapter memory fields.
- Create: `backend/app/models/memory.py` — define `CharacterProfile` and `WorldSetting`.
- Modify: `backend/app/models/__init__.py` — export memory models.
- Modify: `backend/app/main.py` — register memory models and memory router.
- Modify: `backend/app/schemas/novel.py` — add metadata and chapter memory fields to request/response schemas.
- Create: `backend/app/schemas/memory.py` — define character and world setting schemas.
- Modify: `backend/app/repositories/novel_repo.py` — persist new novel/chapter fields.
- Create: `backend/app/repositories/memory_repo.py` — CRUD data access for characters and settings.
- Modify: `backend/app/services/novel_service.py` — pass new fields through existing service boundary.
- Create: `backend/app/services/memory_service.py` — parent ownership checks and memory CRUD logic.
- Create: `backend/app/api/memory.py` — authenticated character and setting endpoints.
- Create: `backend/alembic/versions/8f16e9c1a2b3_phase_1_novel_chapter_fields.py` — novel/chapter field migration.
- Create: `backend/alembic/versions/9a27d4c2b5e6_phase_1_memory_resources.py` — character and world setting table migration.

### Frontend

- Modify: `frontend/src/types/novel.ts` — add novel/chapter fields.
- Create: `frontend/src/types/memory.ts` — character and setting types.
- Modify: `frontend/src/types/index.ts` — export memory types.
- Modify: `frontend/src/api/novels.ts` — keep existing endpoints typed with extended models.
- Create: `frontend/src/api/memory.ts` — character and setting API calls.
- Modify: `frontend/src/stores/novels.ts` — pass extended fields and keep current novel refreshed.
- Create: `frontend/src/stores/memory.ts` — character and setting state/actions.
- Create: `frontend/src/utils/behaviorRules.ts` — split/join behavior rules between textarea and array.
- Create: `frontend/src/__tests__/behaviorRules.spec.ts` — unit tests for behavior rules conversion.
- Create: `frontend/src/components/novels/NovelWorkspaceTabs.vue` — shared current-novel tabs.
- Modify: `frontend/src/router/index.ts` — add character and settings routes.
- Modify: `frontend/src/views/novels/NovelListView.vue` — add `genre` and `style_guide` to create form.
- Modify: `frontend/src/views/novels/NovelDetailView.vue` — add workspace tabs and novel metadata edit modal.
- Modify: `frontend/src/views/editor/EditorView.vue` — add `status` and `summary` editing.
- Create: `frontend/src/views/novels/CharacterListView.vue` — character card CRUD UI.
- Create: `frontend/src/views/novels/WorldSettingsView.vue` — world setting CRUD UI.
- Modify: `frontend/src/__tests__/App.spec.ts` — remove Vite default assertion.
- Modify: `frontend/e2e/vue.spec.ts` — remove Vite default assertion.

---

### Task 1: Backend Test Harness and Novel/Chapter Memory Fields

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_phase_1_manual_memory.py`
- Modify: `backend/app/models/novel.py`
- Modify: `backend/app/schemas/novel.py`
- Modify: `backend/app/repositories/novel_repo.py`
- Modify: `backend/app/services/novel_service.py`
- Modify: `backend/app/api/novels.py`
- Create: `backend/alembic/versions/8f16e9c1a2b3_phase_1_novel_chapter_fields.py`

**Interfaces:**
- Consumes: existing auth endpoints `POST /api/v1/auth/register`, existing novel/chapter endpoints, existing `NovelService` methods.
- Produces: `Novel.genre: str | None`, `Novel.style_guide: str | None`, `Chapter.summary: str`, `Chapter.status: str`, updated novel/chapter API schemas.

- [ ] **Step 1: Add backend test dependencies**

Update `backend/requirements.txt` to include these lines at the end:

```text
pytest>=8.2.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
```

- [ ] **Step 2: Add pytest configuration**

Create `backend/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
pythonpath = .
testpaths = tests
```

- [ ] **Step 3: Add isolated async API test client**

Create `backend/tests/conftest.py`:

```python
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

TEST_DB_PATH = Path(__file__).resolve().parents[1] / "test_novel_agent.db"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret-key"

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Chapter, Novel, User  # noqa: F401, E402


@pytest.fixture(autouse=True)
async def reset_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
```

- [ ] **Step 4: Write failing API test for novel/chapter fields**

Create `backend/tests/test_phase_1_manual_memory.py` with the first test:

```python
async def register_headers(client, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


async def test_novel_and_chapter_manual_memory_fields(client):
    headers = await register_headers(client, "author_one")

    novel_response = await client.post(
        "/api/v1/novels",
        headers=headers,
        json={
            "title": "长夜纪事",
            "description": "边境与皇室的长篇故事",
            "genre": "古风权谋",
            "style_guide": "第三人称有限视角，克制冷调，少用网络化表达。",
        },
    )
    assert novel_response.status_code == 200
    novel = novel_response.json()["data"]
    assert novel["genre"] == "古风权谋"
    assert novel["style_guide"] == "第三人称有限视角，克制冷调，少用网络化表达。"

    updated_response = await client.put(
        f"/api/v1/novels/{novel['id']}",
        headers=headers,
        json={
            "title": "长夜纪事",
            "genre": "古风悬疑",
            "style_guide": "第三人称有限视角，章节末尾保留悬念。",
        },
    )
    assert updated_response.status_code == 200
    updated = updated_response.json()["data"]
    assert updated["genre"] == "古风悬疑"
    assert updated["style_guide"] == "第三人称有限视角，章节末尾保留悬念。"

    chapter_response = await client.post(
        f"/api/v1/novels/{novel['id']}/chapters",
        headers=headers,
        json={
            "title": "第一章 雪线",
            "content": "雪落在城门前。",
            "summary": "女主抵达边城，第一次看见皇室密令。",
            "status": "reviewed",
        },
    )
    assert chapter_response.status_code == 200
    chapter = chapter_response.json()["data"]
    assert chapter["summary"] == "女主抵达边城，第一次看见皇室密令。"
    assert chapter["status"] == "reviewed"

    chapter_update = await client.put(
        f"/api/v1/novels/{novel['id']}/chapters/{chapter['id']}",
        headers=headers,
        json={"summary": "女主抵达边城，并隐约察觉密令与旧案有关。", "status": "locked"},
    )
    assert chapter_update.status_code == 200
    updated_chapter = chapter_update.json()["data"]
    assert updated_chapter["summary"] == "女主抵达边城，并隐约察觉密令与旧案有关。"
    assert updated_chapter["status"] == "locked"
```

- [ ] **Step 5: Run the failing backend test**

Run from `backend/`:

```bash
pytest tests/test_phase_1_manual_memory.py::test_novel_and_chapter_manual_memory_fields -v
```

Expected: FAIL because response data does not include `genre`, `style_guide`, `summary`, and `status` yet.

- [ ] **Step 6: Extend SQLAlchemy models**

Update `backend/app/models/novel.py` to this complete content:

```python
import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    genre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    style_guide: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    user = relationship("User", back_populates="novels")
    chapters = relationship("Chapter", back_populates="novel", order_by="Chapter.created_at")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    novel = relationship("Novel", back_populates="chapters")
```

- [ ] **Step 7: Extend novel/chapter schemas**

Update `backend/app/schemas/novel.py` to include these exact request and response fields:

```python
import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator

ChapterStatus = Literal["draft", "reviewed", "locked"]


class NovelCreate(BaseModel):
    title: str
    description: Optional[str] = None
    genre: Optional[str] = None
    style_guide: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("标题长度不能超过 200 个字符")
        return v

    @field_validator("genre")
    @classmethod
    def validate_genre(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 100:
            raise ValueError("类型长度不能超过 100 个字符")
        return v


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    style_guide: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 200:
            raise ValueError("标题长度不能超过 200 个字符")
        return v

    @field_validator("genre")
    @classmethod
    def validate_genre(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 100:
            raise ValueError("类型长度不能超过 100 个字符")
        return v


class ChapterCreate(BaseModel):
    title: str
    content: str = ""
    summary: str = ""
    status: ChapterStatus = "draft"

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("标题长度不能超过 200 个字符")
        return v


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[ChapterStatus] = None


class ChapterOut(BaseModel):
    id: int
    novel_id: int
    title: str
    content: str
    summary: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class NovelOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    genre: Optional[str]
    style_guide: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    chapters: Optional[List[ChapterOut]] = None

    model_config = {"from_attributes": True}


class NovelListItem(BaseModel):
    id: int
    title: str
    description: Optional[str]
    genre: Optional[str]
    style_guide: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 8: Pass new fields through repository and service**

Update method signatures and assignments in `backend/app/repositories/novel_repo.py`:

```python
async def create(self, user_id: int, title: str, description: Optional[str] = None, genre: Optional[str] = None, style_guide: Optional[str] = None) -> Novel:
    novel = Novel(user_id=user_id, title=title, description=description, genre=genre, style_guide=style_guide)
    self.db.add(novel)
    await self.db.commit()
    await self.db.refresh(novel)
    return novel


async def update(self, novel: Novel, title: Optional[str], description: Optional[str], genre: Optional[str], style_guide: Optional[str]) -> Novel:
    if title is not None:
        novel.title = title
    if description is not None:
        novel.description = description
    if genre is not None:
        novel.genre = genre
    if style_guide is not None:
        novel.style_guide = style_guide
    await self.db.commit()
    await self.db.refresh(novel)
    return novel
```

Update chapter methods in `backend/app/repositories/novel_repo.py`:

```python
async def create(self, novel_id: int, title: str, content: str = "", summary: str = "", status: str = "draft") -> Chapter:
    chapter = Chapter(novel_id=novel_id, title=title, content=content, summary=summary, status=status)
    self.db.add(chapter)
    await self.db.commit()
    await self.db.refresh(chapter)
    return chapter


async def update(self, chapter: Chapter, title: Optional[str], content: Optional[str], summary: Optional[str], status: Optional[str]) -> Chapter:
    if title is not None:
        chapter.title = title
    if content is not None:
        chapter.content = content
    if summary is not None:
        chapter.summary = summary
    if status is not None:
        chapter.status = status
    await self.db.commit()
    await self.db.refresh(chapter)
    return chapter
```

Update `backend/app/services/novel_service.py` method signatures:

```python
async def create(self, user_id: int, title: str, description: Optional[str] = None, genre: Optional[str] = None, style_guide: Optional[str] = None):
    return await self.repo.create(user_id, title, description, genre, style_guide)


async def update(self, user_id: int, novel_id: int, title: Optional[str], description: Optional[str], genre: Optional[str], style_guide: Optional[str]):
    novel = await self.repo.get_by_id(novel_id)
    if not novel:
        raise NotFound("小说不存在")
    if novel.user_id != user_id:
        raise Forbidden("无权修改该小说")
    return await self.repo.update(novel, title, description, genre, style_guide)


async def create_chapter(self, user_id: int, novel_id: int, title: str, content: str = "", summary: str = "", status: str = "draft"):
    novel = await self.repo.get_by_id(novel_id)
    if not novel:
        raise NotFound("小说不存在")
    if novel.user_id != user_id:
        raise Forbidden("无权在该小说下创建章节")
    return await self.chapter_repo.create(novel_id, title, content, summary, status)


async def update_chapter(self, user_id: int, novel_id: int, chapter_id: int, title: Optional[str], content: Optional[str], summary: Optional[str], status: Optional[str]):
    novel = await self.repo.get_by_id(novel_id)
    if not novel:
        raise NotFound("小说不存在")
    if novel.user_id != user_id:
        raise Forbidden("无权修改该章节")
    chapter = await self.chapter_repo.get_by_id(chapter_id)
    if not chapter or chapter.novel_id != novel_id:
        raise NotFound("章节不存在")
    return await self.chapter_repo.update(chapter, title, content, summary, status)
```

- [ ] **Step 9: Pass new fields through API routes**

Update calls in `backend/app/api/novels.py`:

```python
novel = await NovelService(db).create(current_user.id, body.title, body.description, body.genre, body.style_guide)
```

```python
novel = await NovelService(db).update(current_user.id, novel_id, body.title, body.description, body.genre, body.style_guide)
```

```python
chapter = await NovelService(db).create_chapter(current_user.id, novel_id, body.title, body.content, body.summary, body.status)
```

```python
chapter = await NovelService(db).update_chapter(current_user.id, novel_id, chapter_id, body.title, body.content, body.summary, body.status)
```

- [ ] **Step 10: Add Alembic migration**

Create `backend/alembic/versions/8f16e9c1a2b3_phase_1_novel_chapter_fields.py`:

```python
"""phase 1 novel chapter fields

Revision ID: 8f16e9c1a2b3
Revises: 23232ab11c17
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Collection, Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8f16e9c1a2b3"
down_revision: Optional[str] = "23232ab11c17"
branch_labels: Optional[Union[str, Collection[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.add_column("novels", sa.Column("genre", sa.String(length=100), nullable=True))
    op.add_column("novels", sa.Column("style_guide", sa.Text(), nullable=True))
    op.add_column("chapters", sa.Column("summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("chapters", sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"))


def downgrade() -> None:
    op.drop_column("chapters", "status")
    op.drop_column("chapters", "summary")
    op.drop_column("novels", "style_guide")
    op.drop_column("novels", "genre")
```

- [ ] **Step 11: Run the backend test**

Run from `backend/`:

```bash
pytest tests/test_phase_1_manual_memory.py::test_novel_and_chapter_manual_memory_fields -v
```

Expected: PASS.

- [ ] **Step 12: Commit**

```bash
git add backend/requirements.txt backend/pytest.ini backend/tests/conftest.py backend/tests/test_phase_1_manual_memory.py backend/app/models/novel.py backend/app/schemas/novel.py backend/app/repositories/novel_repo.py backend/app/services/novel_service.py backend/app/api/novels.py backend/alembic/versions/8f16e9c1a2b3_phase_1_novel_chapter_fields.py
git commit -m "feat: add manual memory fields to novels and chapters"
```

---

### Task 2: Backend Character and World Setting APIs

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_phase_1_manual_memory.py`
- Create: `backend/app/models/memory.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/memory.py`
- Create: `backend/app/repositories/memory_repo.py`
- Create: `backend/app/services/memory_service.py`
- Create: `backend/app/api/memory.py`
- Modify: `backend/app/main.py`
- Create: `backend/alembic/versions/9a27d4c2b5e6_phase_1_memory_resources.py`

**Interfaces:**
- Consumes: Task 1 test harness, existing auth and novel ownership model.
- Produces: `CharacterProfile` and `WorldSetting` models plus `/api/v1/novels/{novel_id}/characters` and `/api/v1/novels/{novel_id}/settings` endpoints.

- [ ] **Step 1: Extend failing API tests for memory resources**

Append these tests to `backend/tests/test_phase_1_manual_memory.py`:

```python
async def create_novel(client, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/api/v1/novels",
        headers=headers,
        json={"title": "记忆测试小说", "description": "测试"},
    )
    assert response.status_code == 200
    return response.json()["data"]


async def test_character_profile_crud(client):
    headers = await register_headers(client, "character_author")
    novel = await create_novel(client, headers)

    created_response = await client.post(
        f"/api/v1/novels/{novel['id']}/characters",
        headers=headers,
        json={
            "name": "沈照夜",
            "story_role": "男主 / 皇室线关键知情人",
            "identity": "边境军少将军",
            "personality": "克制、谨慎、嘴硬心软",
            "motivation": "查清旧案并保护边境",
            "speech_style": "短句，少解释，紧张时更少称呼。",
            "behavior_rules": ["不会主动背叛朋友", "不会在公开场合示弱"],
            "current_state": "刚与女主建立不稳定同盟",
        },
    )
    assert created_response.status_code == 200
    character = created_response.json()["data"]
    assert character["story_role"] == "男主 / 皇室线关键知情人"
    assert character["identity"] == "边境军少将军"
    assert character["behavior_rules"] == ["不会主动背叛朋友", "不会在公开场合示弱"]

    list_response = await client.get(f"/api/v1/novels/{novel['id']}/characters", headers=headers)
    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()["data"]] == ["沈照夜"]

    update_response = await client.put(
        f"/api/v1/novels/{novel['id']}/characters/{character['id']}",
        headers=headers,
        json={"current_state": "决定暂时相信女主", "behavior_rules": ["不会主动背叛朋友"]},
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["current_state"] == "决定暂时相信女主"
    assert updated["behavior_rules"] == ["不会主动背叛朋友"]

    delete_response = await client.delete(
        f"/api/v1/novels/{novel['id']}/characters/{character['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 200
    empty_response = await client.get(f"/api/v1/novels/{novel['id']}/characters", headers=headers)
    assert empty_response.json()["data"] == []


async def test_world_setting_crud_and_cross_user_protection(client):
    owner_headers = await register_headers(client, "setting_owner")
    other_headers = await register_headers(client, "setting_intruder")
    novel = await create_novel(client, owner_headers)

    created_response = await client.post(
        f"/api/v1/novels/{novel['id']}/settings",
        headers=owner_headers,
        json={"title": "北境军制", "category": "rule", "content": "边境军不受地方节度使调动。"},
    )
    assert created_response.status_code == 200
    setting = created_response.json()["data"]
    assert setting["category"] == "rule"

    blocked_response = await client.get(f"/api/v1/novels/{novel['id']}/settings", headers=other_headers)
    assert blocked_response.status_code == 404

    invalid_response = await client.post(
        f"/api/v1/novels/{novel['id']}/settings",
        headers=owner_headers,
        json={"title": "错误分类", "category": "magic", "content": "无效"},
    )
    assert invalid_response.status_code == 422

    update_response = await client.put(
        f"/api/v1/novels/{novel['id']}/settings/{setting['id']}",
        headers=owner_headers,
        json={"content": "边境军只听虎符和皇令。"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["content"] == "边境军只听虎符和皇令。"

    delete_response = await client.delete(
        f"/api/v1/novels/{novel['id']}/settings/{setting['id']}",
        headers=owner_headers,
    )
    assert delete_response.status_code == 200
```

- [ ] **Step 2: Update test model imports**

Update `backend/tests/conftest.py` import line:

```python
from app.models import Chapter, CharacterProfile, Novel, User, WorldSetting  # noqa: F401, E402
```

- [ ] **Step 3: Run failing memory API tests**

Run from `backend/`:

```bash
pytest tests/test_phase_1_manual_memory.py::test_character_profile_crud tests/test_phase_1_manual_memory.py::test_world_setting_crud_and_cross_user_protection -v
```

Expected: FAIL because memory models and routes do not exist yet.

- [ ] **Step 4: Create memory models**

Create `backend/app/models/memory.py`:

```python
import datetime

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CharacterProfile(Base):
    __tablename__ = "character_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    story_role: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    identity: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    personality: Mapped[str] = mapped_column(Text, nullable=False, default="")
    motivation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    speech_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    behavior_rules: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    current_state: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    novel = relationship("Novel", back_populates="characters")


class WorldSetting(Base):
    __tablename__ = "world_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    novel = relationship("Novel", back_populates="world_settings")
```

- [ ] **Step 5: Export memory models**

Update `backend/app/models/__init__.py`:

```python
from app.models.memory import CharacterProfile, WorldSetting
from app.models.novel import Chapter, Novel
from app.models.user import User

__all__ = ["User", "Novel", "Chapter", "CharacterProfile", "WorldSetting"]
```

- [ ] **Step 6: Create memory schemas**

Create `backend/app/schemas/memory.py`:

```python
import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

WorldSettingCategory = Literal["geography", "faction", "rule", "history", "culture", "other"]


class CharacterCreate(BaseModel):
    name: str
    story_role: str = ""
    identity: str = ""
    personality: str = ""
    motivation: str = ""
    speech_style: str = ""
    behavior_rules: list[str] = Field(default_factory=list)
    current_state: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("角色名不能为空")
        if len(v) > 100:
            raise ValueError("角色名长度不能超过 100 个字符")
        return v


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    story_role: Optional[str] = None
    identity: Optional[str] = None
    personality: Optional[str] = None
    motivation: Optional[str] = None
    speech_style: Optional[str] = None
    behavior_rules: Optional[list[str]] = None
    current_state: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("角色名不能为空")
        if v is not None and len(v) > 100:
            raise ValueError("角色名长度不能超过 100 个字符")
        return v


class CharacterOut(BaseModel):
    id: int
    novel_id: int
    name: str
    story_role: str
    identity: str
    personality: str
    motivation: str
    speech_style: str
    behavior_rules: list[str]
    current_state: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class WorldSettingCreate(BaseModel):
    title: str
    category: WorldSettingCategory = "other"
    content: str = ""

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("设定标题不能为空")
        if len(v) > 200:
            raise ValueError("设定标题长度不能超过 200 个字符")
        return v


class WorldSettingUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[WorldSettingCategory] = None
    content: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("设定标题不能为空")
        if v is not None and len(v) > 200:
            raise ValueError("设定标题长度不能超过 200 个字符")
        return v


class WorldSettingOut(BaseModel):
    id: int
    novel_id: int
    title: str
    category: str
    content: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 7: Add Novel relationships for memory models**

After creating `backend/app/models/memory.py`, add these relationships to `Novel` in `backend/app/models/novel.py` below the existing `chapters` relationship:

```python
    characters = relationship("CharacterProfile", back_populates="novel", cascade="all, delete-orphan")
    world_settings = relationship("WorldSetting", back_populates="novel", cascade="all, delete-orphan")
```

- [ ] **Step 8: Create memory repository**

Create `backend/app/repositories/memory_repo.py`:

```python
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import CharacterProfile, WorldSetting


class CharacterRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int) -> list[CharacterProfile]:
        result = await self.db.execute(select(CharacterProfile).where(CharacterProfile.novel_id == novel_id).order_by(CharacterProfile.updated_at.desc()))
        return list(result.scalars().all())

    async def get_by_id(self, character_id: int) -> Optional[CharacterProfile]:
        return await self.db.get(CharacterProfile, character_id)

    async def create(self, novel_id: int, data: dict) -> CharacterProfile:
        character = CharacterProfile(novel_id=novel_id, **data)
        self.db.add(character)
        await self.db.commit()
        await self.db.refresh(character)
        return character

    async def update(self, character: CharacterProfile, data: dict) -> CharacterProfile:
        for key, value in data.items():
            if value is not None:
                setattr(character, key, value)
        await self.db.commit()
        await self.db.refresh(character)
        return character

    async def delete(self, character: CharacterProfile) -> None:
        await self.db.delete(character)
        await self.db.commit()


class WorldSettingRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int) -> list[WorldSetting]:
        result = await self.db.execute(select(WorldSetting).where(WorldSetting.novel_id == novel_id).order_by(WorldSetting.updated_at.desc()))
        return list(result.scalars().all())

    async def get_by_id(self, setting_id: int) -> Optional[WorldSetting]:
        return await self.db.get(WorldSetting, setting_id)

    async def create(self, novel_id: int, data: dict) -> WorldSetting:
        setting = WorldSetting(novel_id=novel_id, **data)
        self.db.add(setting)
        await self.db.commit()
        await self.db.refresh(setting)
        return setting

    async def update(self, setting: WorldSetting, data: dict) -> WorldSetting:
        for key, value in data.items():
            if value is not None:
                setattr(setting, key, value)
        await self.db.commit()
        await self.db.refresh(setting)
        return setting

    async def delete(self, setting: WorldSetting) -> None:
        await self.db.delete(setting)
        await self.db.commit()
```

- [ ] **Step 9: Create memory service**

Create `backend/app/services/memory_service.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Forbidden, NotFound
from app.repositories.memory_repo import CharacterRepo, WorldSettingRepo
from app.repositories.novel_repo import NovelRepo
from app.schemas.memory import CharacterCreate, CharacterUpdate, WorldSettingCreate, WorldSettingUpdate


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.novel_repo = NovelRepo(db)
        self.character_repo = CharacterRepo(db)
        self.setting_repo = WorldSettingRepo(db)

    async def ensure_owned_novel(self, user_id: int, novel_id: int):
        novel = await self.novel_repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise NotFound("小说不存在")
        return novel

    async def list_characters(self, user_id: int, novel_id: int):
        await self.ensure_owned_novel(user_id, novel_id)
        return await self.character_repo.list_by_novel(novel_id)

    async def create_character(self, user_id: int, novel_id: int, body: CharacterCreate):
        await self.ensure_owned_novel(user_id, novel_id)
        return await self.character_repo.create(novel_id, body.model_dump())

    async def get_character(self, user_id: int, novel_id: int, character_id: int):
        await self.ensure_owned_novel(user_id, novel_id)
        character = await self.character_repo.get_by_id(character_id)
        if not character or character.novel_id != novel_id:
            raise NotFound("角色不存在")
        return character

    async def update_character(self, user_id: int, novel_id: int, character_id: int, body: CharacterUpdate):
        character = await self.get_character(user_id, novel_id, character_id)
        return await self.character_repo.update(character, body.model_dump(exclude_unset=True))

    async def delete_character(self, user_id: int, novel_id: int, character_id: int):
        character = await self.get_character(user_id, novel_id, character_id)
        await self.character_repo.delete(character)

    async def list_settings(self, user_id: int, novel_id: int):
        await self.ensure_owned_novel(user_id, novel_id)
        return await self.setting_repo.list_by_novel(novel_id)

    async def create_setting(self, user_id: int, novel_id: int, body: WorldSettingCreate):
        await self.ensure_owned_novel(user_id, novel_id)
        return await self.setting_repo.create(novel_id, body.model_dump())

    async def get_setting(self, user_id: int, novel_id: int, setting_id: int):
        await self.ensure_owned_novel(user_id, novel_id)
        setting = await self.setting_repo.get_by_id(setting_id)
        if not setting or setting.novel_id != novel_id:
            raise NotFound("设定不存在")
        return setting

    async def update_setting(self, user_id: int, novel_id: int, setting_id: int, body: WorldSettingUpdate):
        setting = await self.get_setting(user_id, novel_id, setting_id)
        return await self.setting_repo.update(setting, body.model_dump(exclude_unset=True))

    async def delete_setting(self, user_id: int, novel_id: int, setting_id: int):
        setting = await self.get_setting(user_id, novel_id, setting_id)
        await self.setting_repo.delete(setting)
```

- [ ] **Step 10: Create memory API routes**

Create `backend/app/api/memory.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.memory import CharacterCreate, CharacterOut, CharacterUpdate, WorldSettingCreate, WorldSettingOut, WorldSettingUpdate
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/novels/{novel_id}", tags=["基础记忆"])


@router.get("/characters")
async def list_characters(novel_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    characters = await MemoryService(db).list_characters(current_user.id, novel_id)
    return ApiResponse.success(data=[CharacterOut.model_validate(c) for c in characters])


@router.post("/characters")
async def create_character(novel_id: int, body: CharacterCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    character = await MemoryService(db).create_character(current_user.id, novel_id, body)
    return ApiResponse.success(data=CharacterOut.model_validate(character), message="角色创建成功")


@router.get("/characters/{character_id}")
async def get_character(novel_id: int, character_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    character = await MemoryService(db).get_character(current_user.id, novel_id, character_id)
    return ApiResponse.success(data=CharacterOut.model_validate(character))


@router.put("/characters/{character_id}")
async def update_character(novel_id: int, character_id: int, body: CharacterUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    character = await MemoryService(db).update_character(current_user.id, novel_id, character_id, body)
    return ApiResponse.success(data=CharacterOut.model_validate(character), message="角色保存成功")


@router.delete("/characters/{character_id}")
async def delete_character(novel_id: int, character_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await MemoryService(db).delete_character(current_user.id, novel_id, character_id)
    return ApiResponse.success(message="角色删除成功")


@router.get("/settings")
async def list_settings(novel_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    settings = await MemoryService(db).list_settings(current_user.id, novel_id)
    return ApiResponse.success(data=[WorldSettingOut.model_validate(s) for s in settings])


@router.post("/settings")
async def create_setting(novel_id: int, body: WorldSettingCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    setting = await MemoryService(db).create_setting(current_user.id, novel_id, body)
    return ApiResponse.success(data=WorldSettingOut.model_validate(setting), message="设定创建成功")


@router.get("/settings/{setting_id}")
async def get_setting(novel_id: int, setting_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    setting = await MemoryService(db).get_setting(current_user.id, novel_id, setting_id)
    return ApiResponse.success(data=WorldSettingOut.model_validate(setting))


@router.put("/settings/{setting_id}")
async def update_setting(novel_id: int, setting_id: int, body: WorldSettingUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    setting = await MemoryService(db).update_setting(current_user.id, novel_id, setting_id, body)
    return ApiResponse.success(data=WorldSettingOut.model_validate(setting), message="设定保存成功")


@router.delete("/settings/{setting_id}")
async def delete_setting(novel_id: int, setting_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await MemoryService(db).delete_setting(current_user.id, novel_id, setting_id)
    return ApiResponse.success(message="设定删除成功")
```

- [ ] **Step 11: Register memory router and models**

Update imports and router registration in `backend/app/main.py`:

```python
from app.models import User, Novel, Chapter, CharacterProfile, WorldSetting  # noqa: F401
from app.api import auth, memory, novels
```

```python
app.include_router(auth.router, prefix="/api/v1")
app.include_router(novels.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
```

- [ ] **Step 12: Add memory resource migration**

Create `backend/alembic/versions/9a27d4c2b5e6_phase_1_memory_resources.py`:

```python
"""phase 1 memory resources

Revision ID: 9a27d4c2b5e6
Revises: 8f16e9c1a2b3
Create Date: 2026-06-26 00:00:01.000000

"""
from typing import Collection, Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9a27d4c2b5e6"
down_revision: Optional[str] = "8f16e9c1a2b3"
branch_labels: Optional[Union[str, Collection[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "character_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("story_role", sa.String(length=200), nullable=False),
        sa.Column("identity", sa.String(length=200), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("motivation", sa.Text(), nullable=False),
        sa.Column("speech_style", sa.Text(), nullable=False),
        sa.Column("behavior_rules", sa.JSON(), nullable=False),
        sa.Column("current_state", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "world_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("world_settings")
    op.drop_table("character_profiles")
```

- [ ] **Step 13: Run all backend tests**

Run from `backend/`:

```bash
pytest -v
```

Expected: PASS for all tests in `backend/tests/test_phase_1_manual_memory.py`.

- [ ] **Step 14: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_phase_1_manual_memory.py backend/app/models/memory.py backend/app/models/__init__.py backend/app/models/novel.py backend/app/schemas/memory.py backend/app/repositories/memory_repo.py backend/app/services/memory_service.py backend/app/api/memory.py backend/app/main.py backend/alembic/versions/9a27d4c2b5e6_phase_1_memory_resources.py
git commit -m "feat: add manual memory APIs"
```

---

### Task 3: Frontend Types, API, Store, and Behavior Rules Utility

**Files:**
- Modify: `frontend/src/types/novel.ts`
- Create: `frontend/src/types/memory.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/novels.ts`
- Create: `frontend/src/api/memory.ts`
- Modify: `frontend/src/stores/novels.ts`
- Create: `frontend/src/stores/memory.ts`
- Create: `frontend/src/utils/behaviorRules.ts`
- Create: `frontend/src/__tests__/behaviorRules.spec.ts`

**Interfaces:**
- Consumes: backend API response shapes from Tasks 1 and 2.
- Produces: typed frontend API calls, `useMemoryStore`, `splitBehaviorRules(input: string): string[]`, `joinBehaviorRules(rules: string[]): string`.

- [ ] **Step 1: Write failing behavior rules unit test**

Create `frontend/src/__tests__/behaviorRules.spec.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { joinBehaviorRules, splitBehaviorRules } from '@/utils/behaviorRules'

describe('behaviorRules utilities', () => {
  it('splits non-empty trimmed lines into rules', () => {
    expect(splitBehaviorRules(' 不会主动背叛朋友 \n\n不会公开示弱\n  ')).toEqual([
      '不会主动背叛朋友',
      '不会公开示弱',
    ])
  })

  it('joins rules with newlines for textarea editing', () => {
    expect(joinBehaviorRules(['不会主动背叛朋友', '不会公开示弱'])).toBe('不会主动背叛朋友\n不会公开示弱')
  })
})
```

- [ ] **Step 2: Run failing frontend unit test**

Run from `frontend/`:

```bash
npm run test:unit -- behaviorRules.spec.ts
```

Expected: FAIL because `@/utils/behaviorRules` does not exist.

- [ ] **Step 3: Add behavior rules utility**

Create `frontend/src/utils/behaviorRules.ts`:

```typescript
export function splitBehaviorRules(input: string): string[] {
  return input
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

export function joinBehaviorRules(rules: string[]): string {
  return rules.join('\n')
}
```

- [ ] **Step 4: Update novel types**

Replace `frontend/src/types/novel.ts` with:

```typescript
export type ChapterStatus = 'draft' | 'reviewed' | 'locked'

export interface NovelCreate {
  title: string
  description?: string | null
  genre?: string | null
  style_guide?: string | null
}

export interface NovelUpdate {
  title?: string | null
  description?: string | null
  genre?: string | null
  style_guide?: string | null
}

export interface NovelListItem {
  id: number
  title: string
  description?: string | null
  genre?: string | null
  style_guide?: string | null
  created_at: string
  updated_at: string
}

export interface ChapterCreate {
  title: string
  content?: string
  summary?: string
  status?: ChapterStatus
}

export interface ChapterUpdate {
  title?: string | null
  content?: string | null
  summary?: string | null
  status?: ChapterStatus | null
}

export interface ChapterOut {
  id: number
  novel_id: number
  title: string
  content: string
  summary: string
  status: ChapterStatus
  created_at: string
  updated_at: string
}

export interface NovelOut extends NovelListItem {
  chapters?: ChapterOut[]
}
```

- [ ] **Step 5: Add memory types and export them**

Create `frontend/src/types/memory.ts`:

```typescript
export type WorldSettingCategory = 'geography' | 'faction' | 'rule' | 'history' | 'culture' | 'other'

export interface CharacterProfile {
  id: number
  novel_id: number
  name: string
  story_role: string
  identity: string
  personality: string
  motivation: string
  speech_style: string
  behavior_rules: string[]
  current_state: string
  created_at: string
  updated_at: string
}

export interface CharacterCreate {
  name: string
  story_role?: string
  identity?: string
  personality?: string
  motivation?: string
  speech_style?: string
  behavior_rules?: string[]
  current_state?: string
}

export interface CharacterUpdate {
  name?: string | null
  story_role?: string | null
  identity?: string | null
  personality?: string | null
  motivation?: string | null
  speech_style?: string | null
  behavior_rules?: string[] | null
  current_state?: string | null
}

export interface WorldSetting {
  id: number
  novel_id: number
  title: string
  category: WorldSettingCategory
  content: string
  created_at: string
  updated_at: string
}

export interface WorldSettingCreate {
  title: string
  category: WorldSettingCategory
  content?: string
}

export interface WorldSettingUpdate {
  title?: string | null
  category?: WorldSettingCategory | null
  content?: string | null
}
```

Update `frontend/src/types/index.ts`:

```typescript
export * from './api'
export * from './auth'
export * from './memory'
export * from './novel'
```

- [ ] **Step 6: Add memory API calls**

Create `frontend/src/api/memory.ts`:

```typescript
import client from './client'
import type { CharacterCreate, CharacterProfile, CharacterUpdate, WorldSetting, WorldSettingCreate, WorldSettingUpdate } from '@/types'

export function listCharacters(novelId: number): Promise<CharacterProfile[]> { return client.get(`/novels/${novelId}/characters`) }
export function createCharacter(novelId: number, data: CharacterCreate): Promise<CharacterProfile> { return client.post(`/novels/${novelId}/characters`, data) }
export function getCharacter(novelId: number, characterId: number): Promise<CharacterProfile> { return client.get(`/novels/${novelId}/characters/${characterId}`) }
export function updateCharacter(novelId: number, characterId: number, data: CharacterUpdate): Promise<CharacterProfile> { return client.put(`/novels/${novelId}/characters/${characterId}`, data) }
export function deleteCharacter(novelId: number, characterId: number): Promise<void> { return client.delete(`/novels/${novelId}/characters/${characterId}`) }

export function listWorldSettings(novelId: number): Promise<WorldSetting[]> { return client.get(`/novels/${novelId}/settings`) }
export function createWorldSetting(novelId: number, data: WorldSettingCreate): Promise<WorldSetting> { return client.post(`/novels/${novelId}/settings`, data) }
export function getWorldSetting(novelId: number, settingId: number): Promise<WorldSetting> { return client.get(`/novels/${novelId}/settings/${settingId}`) }
export function updateWorldSetting(novelId: number, settingId: number, data: WorldSettingUpdate): Promise<WorldSetting> { return client.put(`/novels/${novelId}/settings/${settingId}`, data) }
export function deleteWorldSetting(novelId: number, settingId: number): Promise<void> { return client.delete(`/novels/${novelId}/settings/${settingId}`) }
```

- [ ] **Step 7: Add memory store**

Create `frontend/src/stores/memory.ts`:

```typescript
import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as memoryApi from '@/api/memory'
import type { CharacterCreate, CharacterProfile, CharacterUpdate, WorldSetting, WorldSettingCreate, WorldSettingUpdate } from '@/types'

export const useMemoryStore = defineStore('memory', () => {
  const characters = ref<CharacterProfile[]>([])
  const worldSettings = ref<WorldSetting[]>([])

  async function loadCharacters(novelId: number) { characters.value = await memoryApi.listCharacters(novelId) }
  async function createCharacter(novelId: number, data: CharacterCreate) { const item = await memoryApi.createCharacter(novelId, data); characters.value.unshift(item) }
  async function updateCharacter(novelId: number, characterId: number, data: CharacterUpdate) { const item = await memoryApi.updateCharacter(novelId, characterId, data); characters.value = characters.value.map((c) => c.id === characterId ? item : c) }
  async function deleteCharacter(novelId: number, characterId: number) { await memoryApi.deleteCharacter(novelId, characterId); characters.value = characters.value.filter((c) => c.id !== characterId) }

  async function loadWorldSettings(novelId: number) { worldSettings.value = await memoryApi.listWorldSettings(novelId) }
  async function createWorldSetting(novelId: number, data: WorldSettingCreate) { const item = await memoryApi.createWorldSetting(novelId, data); worldSettings.value.unshift(item) }
  async function updateWorldSetting(novelId: number, settingId: number, data: WorldSettingUpdate) { const item = await memoryApi.updateWorldSetting(novelId, settingId, data); worldSettings.value = worldSettings.value.map((s) => s.id === settingId ? item : s) }
  async function deleteWorldSetting(novelId: number, settingId: number) { await memoryApi.deleteWorldSetting(novelId, settingId); worldSettings.value = worldSettings.value.filter((s) => s.id !== settingId) }

  return { characters, worldSettings, loadCharacters, createCharacter, updateCharacter, deleteCharacter, loadWorldSettings, createWorldSetting, updateWorldSetting, deleteWorldSetting }
})
```

- [ ] **Step 8: Keep novel store compatible with extended fields**

No new state is required in `frontend/src/stores/novels.ts`. Ensure imports still compile with extended `NovelCreate`, `NovelUpdate`, `ChapterCreate`, and `ChapterUpdate` types from `@/types`.

- [ ] **Step 9: Run unit test and type check**

Run from `frontend/`:

```bash
npm run test:unit -- behaviorRules.spec.ts
npm run type-check
```

Expected: behavior rules tests PASS and type-check PASS.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/types/novel.ts frontend/src/types/memory.ts frontend/src/types/index.ts frontend/src/api/memory.ts frontend/src/stores/memory.ts frontend/src/utils/behaviorRules.ts frontend/src/__tests__/behaviorRules.spec.ts frontend/src/stores/novels.ts frontend/src/api/novels.ts
git commit -m "feat: add frontend manual memory contracts"
```

---

### Task 4: Frontend Workspace Navigation and Extended Novel/Chapter Editing

**Files:**
- Create: `frontend/src/components/novels/NovelWorkspaceTabs.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/novels/NovelListView.vue`
- Modify: `frontend/src/views/novels/NovelDetailView.vue`
- Modify: `frontend/src/views/editor/EditorView.vue`

**Interfaces:**
- Consumes: extended novel/chapter types and API from Task 3.
- Produces: current-novel tabs, novel metadata create/edit fields, and chapter `summary`/`status` editing.

- [ ] **Step 1: Add workspace tabs component**

Create `frontend/src/components/novels/NovelWorkspaceTabs.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps<{ novelId: number }>()
const route = useRoute()
const router = useRouter()

const tabs = computed(() => [
  { label: '章节', path: `/novels/${props.novelId}` },
  { label: '角色', path: `/novels/${props.novelId}/characters` },
  { label: '设定', path: `/novels/${props.novelId}/settings` },
])
</script>

<template>
  <nav class="workspace-tabs">
    <button v-for="tab in tabs" :key="tab.path" class="workspace-tabs__item" :class="{ 'workspace-tabs__item--active': route.path === tab.path }" @click="router.push(tab.path)">
      {{ tab.label }}
    </button>
  </nav>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.workspace-tabs { display: flex; gap: $spacing-sm; margin-bottom: $spacing-lg; border-bottom: 1px solid $color-border; }
.workspace-tabs__item { padding: $spacing-sm $spacing-md; color: $color-text-secondary; border-bottom: 2px solid transparent; font-size: $font-size-sm; }
.workspace-tabs__item:hover { color: $color-text; }
.workspace-tabs__item--active { color: $color-primary-dark; border-bottom-color: $color-primary; font-weight: 600; }
</style>
```

- [ ] **Step 2: Add routes**

Update route array in `frontend/src/router/index.ts` to include:

```typescript
{ path: '/novels/:id/characters', name: 'novel-characters', component: () => import('@/views/novels/CharacterListView.vue'), meta: { auth: true } },
{ path: '/novels/:id/settings', name: 'novel-settings', component: () => import('@/views/novels/WorldSettingsView.vue'), meta: { auth: true } },
```

Place them after the existing `/novels/:id` route and before the editor route.

- [ ] **Step 3: Extend novel creation form**

In `frontend/src/views/novels/NovelListView.vue`, add refs:

```typescript
const newGenre = ref('')
const newStyleGuide = ref('')
```

Update `handleCreate()` payload and reset logic:

```typescript
await novelStore.createNovel({
  title: newTitle.value,
  description: newDescription.value || null,
  genre: newGenre.value || null,
  style_guide: newStyleGuide.value || null,
})
showCreateModal.value = false
newTitle.value = ''
newDescription.value = ''
newGenre.value = ''
newStyleGuide.value = ''
```

Add these fields inside the create modal after description:

```vue
<div style="height:12px" />
<AppInput v-model="newGenre" placeholder="小说类型（可选）" />
<div style="height:12px" />
<AppTextarea v-model="newStyleGuide" placeholder="风格指南（可选）" :rows="4" />
```

- [ ] **Step 4: Add workspace tabs and novel metadata editing to detail page**

In `frontend/src/views/novels/NovelDetailView.vue`, import `AppTextarea` and `NovelWorkspaceTabs`:

```typescript
import AppTextarea from '@/components/common/AppTextarea.vue'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'
```

Add metadata edit refs and functions:

```typescript
const showNovelModal = ref(false)
const editTitle = ref('')
const editDescription = ref('')
const editGenre = ref('')
const editStyleGuide = ref('')

function openNovelModal() {
  const novel = novelStore.currentNovel
  if (!novel) return
  editTitle.value = novel.title
  editDescription.value = novel.description || ''
  editGenre.value = novel.genre || ''
  editStyleGuide.value = novel.style_guide || ''
  showNovelModal.value = true
}

async function handleUpdateNovel() {
  if (!editTitle.value) return
  await novelStore.updateNovel(novelId.value, {
    title: editTitle.value,
    description: editDescription.value || null,
    genre: editGenre.value || null,
    style_guide: editStyleGuide.value || null,
  })
  showNovelModal.value = false
}
```

Render tabs at the top of the page content:

```vue
<NovelWorkspaceTabs :novel-id="novelId" />
```

Add an edit button near the novel title:

```vue
<AppButton size="sm" variant="secondary" @click="openNovelModal">编辑信息</AppButton>
```

Add metadata display below the title area:

```vue
<div class="novel-detail__meta">
  <span v-if="novelStore.currentNovel.genre">类型：{{ novelStore.currentNovel.genre }}</span>
  <span v-if="novelStore.currentNovel.style_guide">风格指南：{{ novelStore.currentNovel.style_guide }}</span>
</div>
```

Add edit modal near existing modals:

```vue
<AppModal v-model:visible="showNovelModal" title="编辑小说信息" confirm-text="保存" cancel-text="取消" @confirm="handleUpdateNovel" @cancel="showNovelModal = false">
  <AppInput v-model="editTitle" placeholder="小说标题" />
  <div style="height:12px" />
  <AppTextarea v-model="editDescription" placeholder="小说简介" :rows="3" />
  <div style="height:12px" />
  <AppInput v-model="editGenre" placeholder="小说类型" />
  <div style="height:12px" />
  <AppTextarea v-model="editStyleGuide" placeholder="风格指南" :rows="4" />
</AppModal>
```

- [ ] **Step 5: Add summary and status to editor**

In `frontend/src/views/editor/EditorView.vue`, add status and summary state:

```typescript
import type { ChapterStatus } from '@/types'

const summary = ref('')
const status = ref<ChapterStatus>('draft')
```

After loading current chapter, set:

```typescript
summary.value = novelStore.currentChapter.summary
status.value = novelStore.currentChapter.status
```

Update save payload:

```typescript
await novelStore.updateChapter(novelId.value, chapterId.value, {
  title: title.value,
  content: content.value,
  summary: summary.value,
  status: status.value,
})
```

Add status select in the header before save button:

```vue
<select v-model="status" class="editor__status">
  <option value="draft">草稿</option>
  <option value="reviewed">已确认</option>
  <option value="locked">锁定</option>
</select>
```

Add summary textarea below body content:

```vue
<section class="editor__summary">
  <h3 class="editor__summary-title">章节摘要</h3>
  <AppTextarea v-model="summary" placeholder="手动记录本章关键事实、角色变化和后续需要记住的信息" :rows="5" />
</section>
```

Add styles:

```scss
&__status { border: 1px solid $color-border; border-radius: $radius-md; padding: 4px 8px; background: $color-bg-card; color: $color-text; }
&__summary { border-top: 1px solid $color-border; padding-top: $spacing-lg; }
&__summary-title { font-size: $font-size-md; font-weight: 600; margin-bottom: $spacing-sm; }
```

- [ ] **Step 6: Run frontend verification**

Run from `frontend/`:

```bash
npm run type-check
npm run build
```

Expected: both commands PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/novels/NovelWorkspaceTabs.vue frontend/src/router/index.ts frontend/src/views/novels/NovelListView.vue frontend/src/views/novels/NovelDetailView.vue frontend/src/views/editor/EditorView.vue
git commit -m "feat: add novel workspace metadata editing"
```

---

### Task 5: Frontend Character Management Page

**Files:**
- Create: `frontend/src/views/novels/CharacterListView.vue`

**Interfaces:**
- Consumes: `useNovelStore`, `useMemoryStore`, `NovelWorkspaceTabs`, `splitBehaviorRules`, `joinBehaviorRules`.
- Produces: `/novels/:id/characters` page with character CRUD.

- [ ] **Step 1: Create character page**

Create `frontend/src/views/novels/CharacterListView.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import AppCard from '@/components/common/AppCard.vue'
import AppConfirm from '@/components/common/AppConfirm.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import AppInput from '@/components/common/AppInput.vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppTextarea from '@/components/common/AppTextarea.vue'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'
import { useMemoryStore } from '@/stores/memory'
import { useNovelStore } from '@/stores/novels'
import type { CharacterProfile } from '@/types'
import { joinBehaviorRules, splitBehaviorRules } from '@/utils/behaviorRules'

const route = useRoute()
const novelStore = useNovelStore()
const memoryStore = useMemoryStore()
const novelId = computed(() => Number(route.params.id))
const showModal = ref(false)
const editingId = ref<number | null>(null)
const deleteTarget = ref<number | null>(null)
const form = ref({ name: '', story_role: '', identity: '', personality: '', motivation: '', speech_style: '', behavior_rules_text: '', current_state: '' })

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  await memoryStore.loadCharacters(novelId.value)
})

function openCreate() {
  editingId.value = null
  form.value = { name: '', story_role: '', identity: '', personality: '', motivation: '', speech_style: '', behavior_rules_text: '', current_state: '' }
  showModal.value = true
}

function openEdit(character: CharacterProfile) {
  editingId.value = character.id
  form.value = {
    name: character.name,
    story_role: character.story_role,
    identity: character.identity,
    personality: character.personality,
    motivation: character.motivation,
    speech_style: character.speech_style,
    behavior_rules_text: joinBehaviorRules(character.behavior_rules),
    current_state: character.current_state,
  }
  showModal.value = true
}

async function handleSave() {
  if (!form.value.name) return
  const payload = {
    name: form.value.name,
    story_role: form.value.story_role,
    identity: form.value.identity,
    personality: form.value.personality,
    motivation: form.value.motivation,
    speech_style: form.value.speech_style,
    behavior_rules: splitBehaviorRules(form.value.behavior_rules_text),
    current_state: form.value.current_state,
  }
  if (editingId.value) await memoryStore.updateCharacter(novelId.value, editingId.value, payload)
  else await memoryStore.createCharacter(novelId.value, payload)
  showModal.value = false
}

async function handleDelete() {
  if (deleteTarget.value === null) return
  await memoryStore.deleteCharacter(novelId.value, deleteTarget.value)
  deleteTarget.value = null
}
</script>

<template>
  <AppLayout>
    <div class="characters">
      <NovelWorkspaceTabs :novel-id="novelId" />
      <div class="characters__header">
        <div>
          <h2 class="characters__title">角色卡片</h2>
          <p class="characters__subtitle">{{ novelStore.currentNovel?.title }}</p>
        </div>
        <AppButton size="sm" @click="openCreate">新建角色</AppButton>
      </div>

      <AppEmpty v-if="memoryStore.characters.length === 0" text="暂无角色卡" />
      <div v-else class="characters__grid">
        <AppCard v-for="character in memoryStore.characters" :key="character.id" class="character-card">
          <div class="character-card__header">
            <h3>{{ character.name }}</h3>
            <div class="character-card__actions">
              <button @click="openEdit(character)">编辑</button>
              <button @click="deleteTarget = character.id">删除</button>
            </div>
          </div>
          <p v-if="character.story_role"><strong>叙事功能：</strong>{{ character.story_role }}</p>
          <p v-if="character.identity"><strong>身份：</strong>{{ character.identity }}</p>
          <p v-if="character.personality"><strong>性格：</strong>{{ character.personality }}</p>
          <p v-if="character.motivation"><strong>动机：</strong>{{ character.motivation }}</p>
          <p v-if="character.speech_style"><strong>说话方式：</strong>{{ character.speech_style }}</p>
          <p v-if="character.current_state"><strong>当前状态：</strong>{{ character.current_state }}</p>
          <ul v-if="character.behavior_rules.length" class="character-card__rules">
            <li v-for="rule in character.behavior_rules" :key="rule">{{ rule }}</li>
          </ul>
        </AppCard>
      </div>

      <AppModal v-model:visible="showModal" :title="editingId ? '编辑角色' : '新建角色'" confirm-text="保存" cancel-text="取消" width="720px" @confirm="handleSave" @cancel="showModal = false">
        <div class="characters__form">
          <AppInput v-model="form.name" placeholder="角色名" />
          <AppInput v-model="form.story_role" placeholder="叙事功能，如主角 / 反派 / 导师" />
          <AppInput v-model="form.identity" placeholder="世界内身份，如边境军少将军" />
          <AppTextarea v-model="form.personality" placeholder="性格特征" :rows="3" />
          <AppTextarea v-model="form.motivation" placeholder="动机和目标" :rows="3" />
          <AppTextarea v-model="form.speech_style" placeholder="说话方式约束" :rows="3" />
          <AppTextarea v-model="form.behavior_rules_text" placeholder="行为边界，每行一条" :rows="4" />
          <AppTextarea v-model="form.current_state" placeholder="当前状态" :rows="3" />
        </div>
      </AppModal>

      <AppConfirm v-model:visible="deleteTarget !== null" title="删除角色" content="确定要删除这个角色卡吗？" confirm-text="删除" confirm-variant="danger" @confirm="handleDelete" @cancel="deleteTarget = null" />
    </div>
  </AppLayout>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.characters { max-width: 1100px; margin: 0 auto; }
.characters__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: $spacing-lg; }
.characters__title { font-size: $font-size-xl; font-weight: 700; }
.characters__subtitle { margin-top: $spacing-xs; color: $color-text-secondary; font-size: $font-size-sm; }
.characters__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: $spacing-md; }
.characters__form { display: flex; flex-direction: column; gap: $spacing-md; }
.character-card { display: flex; flex-direction: column; gap: $spacing-sm; }
.character-card__header { display: flex; justify-content: space-between; gap: $spacing-md; }
.character-card__actions { display: flex; gap: $spacing-sm; font-size: $font-size-sm; color: $color-primary-dark; }
.character-card p { font-size: $font-size-sm; line-height: 1.7; color: $color-text-secondary; }
.character-card__rules { padding-left: $spacing-lg; color: $color-text-secondary; font-size: $font-size-sm; line-height: 1.7; }
</style>
```

- [ ] **Step 2: Run frontend verification**

Run from `frontend/`:

```bash
npm run type-check
npm run build
```

Expected: both commands PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/novels/CharacterListView.vue
git commit -m "feat: add character management page"
```

---

### Task 6: Frontend World Settings Management Page

**Files:**
- Create: `frontend/src/views/novels/WorldSettingsView.vue`

**Interfaces:**
- Consumes: `useNovelStore`, `useMemoryStore`, `NovelWorkspaceTabs`, `WorldSettingCategory`.
- Produces: `/novels/:id/settings` page with world setting CRUD and category filtering.

- [ ] **Step 1: Create world settings page**

Create `frontend/src/views/novels/WorldSettingsView.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import AppCard from '@/components/common/AppCard.vue'
import AppConfirm from '@/components/common/AppConfirm.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import AppInput from '@/components/common/AppInput.vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppTextarea from '@/components/common/AppTextarea.vue'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'
import { useMemoryStore } from '@/stores/memory'
import { useNovelStore } from '@/stores/novels'
import type { WorldSetting, WorldSettingCategory } from '@/types'

const route = useRoute()
const novelStore = useNovelStore()
const memoryStore = useMemoryStore()
const novelId = computed(() => Number(route.params.id))
const showModal = ref(false)
const editingId = ref<number | null>(null)
const deleteTarget = ref<number | null>(null)
const selectedCategory = ref<WorldSettingCategory | 'all'>('all')
const form = ref<{ title: string; category: WorldSettingCategory; content: string }>({ title: '', category: 'other', content: '' })

const categories: { value: WorldSettingCategory | 'all'; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'geography', label: '地理' },
  { value: 'faction', label: '势力' },
  { value: 'rule', label: '规则' },
  { value: 'history', label: '历史' },
  { value: 'culture', label: '文化' },
  { value: 'other', label: '其他' },
]

const filteredSettings = computed(() => selectedCategory.value === 'all'
  ? memoryStore.worldSettings
  : memoryStore.worldSettings.filter((item) => item.category === selectedCategory.value))

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  await memoryStore.loadWorldSettings(novelId.value)
})

function categoryLabel(category: string) {
  return categories.find((item) => item.value === category)?.label || category
}

function openCreate() {
  editingId.value = null
  form.value = { title: '', category: 'other', content: '' }
  showModal.value = true
}

function openEdit(setting: WorldSetting) {
  editingId.value = setting.id
  form.value = { title: setting.title, category: setting.category, content: setting.content }
  showModal.value = true
}

async function handleSave() {
  if (!form.value.title) return
  if (editingId.value) await memoryStore.updateWorldSetting(novelId.value, editingId.value, form.value)
  else await memoryStore.createWorldSetting(novelId.value, form.value)
  showModal.value = false
}

async function handleDelete() {
  if (deleteTarget.value === null) return
  await memoryStore.deleteWorldSetting(novelId.value, deleteTarget.value)
  deleteTarget.value = null
}
</script>

<template>
  <AppLayout>
    <div class="settings">
      <NovelWorkspaceTabs :novel-id="novelId" />
      <div class="settings__header">
        <div>
          <h2 class="settings__title">世界观设定</h2>
          <p class="settings__subtitle">{{ novelStore.currentNovel?.title }}</p>
        </div>
        <AppButton size="sm" @click="openCreate">新建设定</AppButton>
      </div>

      <div class="settings__filters">
        <button v-for="category in categories" :key="category.value" class="settings__filter" :class="{ 'settings__filter--active': selectedCategory === category.value }" @click="selectedCategory = category.value">
          {{ category.label }}
        </button>
      </div>

      <AppEmpty v-if="filteredSettings.length === 0" text="暂无世界观设定" />
      <div v-else class="settings__grid">
        <AppCard v-for="setting in filteredSettings" :key="setting.id" class="setting-card">
          <div class="setting-card__header">
            <div>
              <h3>{{ setting.title }}</h3>
              <span>{{ categoryLabel(setting.category) }}</span>
            </div>
            <div class="setting-card__actions">
              <button @click="openEdit(setting)">编辑</button>
              <button @click="deleteTarget = setting.id">删除</button>
            </div>
          </div>
          <p>{{ setting.content }}</p>
        </AppCard>
      </div>

      <AppModal v-model:visible="showModal" :title="editingId ? '编辑设定' : '新建设定'" confirm-text="保存" cancel-text="取消" width="640px" @confirm="handleSave" @cancel="showModal = false">
        <div class="settings__form">
          <AppInput v-model="form.title" placeholder="设定标题" />
          <select v-model="form.category" class="settings__select">
            <option value="geography">地理</option>
            <option value="faction">势力</option>
            <option value="rule">规则</option>
            <option value="history">历史</option>
            <option value="culture">文化</option>
            <option value="other">其他</option>
          </select>
          <AppTextarea v-model="form.content" placeholder="设定内容" :rows="8" />
        </div>
      </AppModal>

      <AppConfirm v-model:visible="deleteTarget !== null" title="删除设定" content="确定要删除这条世界观设定吗？" confirm-text="删除" confirm-variant="danger" @confirm="handleDelete" @cancel="deleteTarget = null" />
    </div>
  </AppLayout>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.settings { max-width: 1100px; margin: 0 auto; }
.settings__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: $spacing-lg; }
.settings__title { font-size: $font-size-xl; font-weight: 700; }
.settings__subtitle { margin-top: $spacing-xs; color: $color-text-secondary; font-size: $font-size-sm; }
.settings__filters { display: flex; flex-wrap: wrap; gap: $spacing-sm; margin-bottom: $spacing-lg; }
.settings__filter { padding: 4px 12px; border-radius: $radius-md; background: $color-bg-card; color: $color-text-secondary; border: 1px solid $color-border; }
.settings__filter--active { background: $color-primary; color: #fff; border-color: $color-primary; }
.settings__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: $spacing-md; }
.settings__form { display: flex; flex-direction: column; gap: $spacing-md; }
.settings__select { border: 1px solid $color-border; border-radius: $radius-md; padding: 8px 16px; background: $color-bg-card; color: $color-text; }
.setting-card { display: flex; flex-direction: column; gap: $spacing-sm; }
.setting-card__header { display: flex; justify-content: space-between; gap: $spacing-md; }
.setting-card__header span { display: inline-block; margin-top: 4px; color: $color-primary-dark; font-size: $font-size-xs; }
.setting-card__actions { display: flex; gap: $spacing-sm; font-size: $font-size-sm; color: $color-primary-dark; }
.setting-card p { font-size: $font-size-sm; line-height: 1.8; white-space: pre-wrap; color: $color-text-secondary; }
</style>
```

- [ ] **Step 2: Run frontend verification**

Run from `frontend/`:

```bash
npm run type-check
npm run build
```

Expected: both commands PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/novels/WorldSettingsView.vue
git commit -m "feat: add world settings management page"
```

---

### Task 7: Test Cleanup and End-to-End Verification

**Files:**
- Modify: `frontend/src/__tests__/App.spec.ts`
- Modify: `frontend/e2e/vue.spec.ts`

**Interfaces:**
- Consumes: current app shell, login route, previous backend/frontend work.
- Produces: meaningful frontend baseline tests and full verification commands.

- [ ] **Step 1: Replace App unit test**

Replace `frontend/src/__tests__/App.spec.ts` with:

```typescript
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import App from '../App.vue'

describe('App', () => {
  it('mounts the router outlet', () => {
    const wrapper = mount(App, {
      global: {
        plugins: [createPinia()],
        stubs: ['router-view'],
      },
    })

    expect(wrapper.exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Replace E2E smoke test**

Replace `frontend/e2e/vue.spec.ts` with:

```typescript
import { test, expect } from '@playwright/test'

test('shows login page for unauthenticated users', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByText('登录你的账号')).toBeVisible()
})
```

- [ ] **Step 3: Run complete backend verification**

Run from `backend/`:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 4: Run complete frontend verification**

Run from `frontend/`:

```bash
npm run test:unit
npm run type-check
npm run build
npm run test:e2e -- --project=chromium
```

Expected: all commands PASS.

- [ ] **Step 5: Inspect worktree**

Run from repo root:

```bash
git status --short
```

Expected: only files intentionally changed by this plan are listed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/__tests__/App.spec.ts frontend/e2e/vue.spec.ts
git commit -m "fix: update frontend smoke tests"
```

---

## Final Verification Checklist

Run these commands before claiming completion:

```bash
pytest -v
```

from `backend/`, and:

```bash
npm run test:unit
npm run type-check
npm run build
npm run test:e2e -- --project=chromium
```

from `frontend/`.

Manual browser check:

1. Register or log in.
2. Create a novel with title, description, genre, and style guide.
3. Create a chapter, edit title/content/summary/status, and save.
4. Open the novel workspace `章节 | 角色 | 设定` tabs.
5. Create, edit, and delete a character card.
6. Create, filter, edit, and delete a world setting.
