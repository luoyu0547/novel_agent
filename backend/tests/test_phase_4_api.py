"""Phase 4 API 路由 HTTP 契约测试。

覆盖所有端点的成功路径和错误场景：
- 认证缺失返回 401
- 其他用户资源返回 404
- 版本跨 run 使用返回 400
- 过期修订序列返回 400
- 无效请求体返回 422
- 未确认扩大范围返回 400
- 已接受/已丢弃/已锁定写入返回 400
- 所有成功响应含 code=0, message, typed data
"""

import pytest
from fastapi import Depends
from httpx import AsyncClient

from app.ai.modification import (
    FakeModificationAgent,
    ModificationOutput,
    RepairOption,
    RepairOptionsOutput,
    RevisionPatch,
)
from app.api.revisions import get_modification_service
from app.core.database import async_session_factory, get_db
from app.core.security import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.draft_version import DraftVersion
from app.models.novel import Chapter, Novel
from app.models.plot_planning import DraftRevision
from app.models.quality_gate import ReviewIssue
from app.models.user import User
from app.models.writing import ChapterBrief, ChapterPlan, ContextPackage, WritingRun
from app.services.draft_version_service import DraftVersionService
from app.services.modification_service import ModificationService


# ── Helpers ──────────────────────────────────────────────────────────


async def _register_and_create_novel(client: AsyncClient, username: str = "p4_tester"):
    """Register a user and create a novel, return (novel, headers)."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    token = resp.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/v1/novels",
        headers=headers,
        json={"title": "P4测试", "description": "Phase 4 API测试", "genre": "古风"},
    )
    novel = resp.json()["data"]
    return novel, headers, token


async def _create_full_chain(client: AsyncClient, novel_id: int, headers: dict):
    """Create blueprint -> chapter plan -> chapter brief -> context package -> writing run via API.

    Returns the writing run data from the API response.
    """
    # Generate blueprint
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    blueprint = resp.json()["data"]

    # Generate chapter plan
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-plans/next/generate",
        headers=headers,
    )
    plan = resp.json()["data"]

    # Generate chapter brief
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-briefs/generate",
        headers=headers,
        json={"chapter_plan_id": plan["id"]},
    )
    brief = resp.json()["data"]

    # Generate context package
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/context-packages/generate",
        headers=headers,
        json={"chapter_brief_id": brief["id"]},
    )
    ctx = resp.json()["data"]

    # Create writing run (using FakeWritingGenerator via conftest env)
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/writing-runs",
        headers=headers,
        json={"chapter_brief_id": brief["id"], "context_package_id": ctx["id"]},
    )
    run = resp.json()["data"]
    return run


async def _setup_run_with_version_db(
    draft_content: str = "这是一段测试正文，用于验证Phase4的API功能。",
    run_status: str = "completed",
):
    """Directly create run + DraftVersion in DB (no API calls needed)."""
    async with async_session_factory() as db:
        user = User(username=f"dbuser_{id(draft_content)}", hashed_password="x")
        db.add(user)
        await db.flush()

        novel = Novel(
            title="DB测试小说",
            description="",
            genre="古风",
            style_guide="第三人称",
            user_id=user.id,
        )
        db.add(novel)
        await db.flush()

        cp = ChapterPlan(novel_id=novel.id, position=1)
        db.add(cp)
        await db.flush()
        cb = ChapterBrief(novel_id=novel.id, chapter_plan_id=cp.id)
        db.add(cb)
        await db.flush()
        ctx = ContextPackage(novel_id=novel.id, chapter_brief_id=cb.id)
        db.add(ctx)
        await db.flush()

        run = WritingRun(
            novel_id=novel.id,
            chapter_brief_id=cb.id,
            context_package_id=ctx.id,
            draft_content=draft_content,
            status=run_status,
        )
        db.add(run)
        await db.flush()

        svc = DraftVersionService(db, user.id, novel.id)
        version = await svc.ensure_initial_version(run)
        await db.commit()

        return {
            "user_id": user.id,
            "novel_id": novel.id,
            "run_id": run.id,
            "version_id": version.id,
        }


async def _setup_run_with_issue_db(
    draft_content: str = "这是一段测试正文，用于验证修改服务的功能。",
    issue_location: str = "测试正文",
):
    """Directly create run + DraftVersion + ReviewIssue in DB."""
    async with async_session_factory() as db:
        user = User(username=f"issueuser_{id(draft_content)}", hashed_password="x")
        db.add(user)
        await db.flush()

        novel = Novel(
            title="Issue测试小说",
            description="",
            genre="古风",
            style_guide="第三人称",
            user_id=user.id,
        )
        db.add(novel)
        await db.flush()

        cp = ChapterPlan(novel_id=novel.id, position=1)
        db.add(cp)
        await db.flush()
        cb = ChapterBrief(novel_id=novel.id, chapter_plan_id=cp.id)
        db.add(cb)
        await db.flush()
        ctx = ContextPackage(novel_id=novel.id, chapter_brief_id=cb.id)
        db.add(ctx)
        await db.flush()

        run = WritingRun(
            novel_id=novel.id,
            chapter_brief_id=cb.id,
            context_package_id=ctx.id,
            draft_content=draft_content,
            status="completed",
        )
        db.add(run)
        await db.flush()

        svc = DraftVersionService(db, user.id, novel.id)
        version = await svc.ensure_initial_version(run)

        from app.repositories.quality_gate_repo import ReviewIssueRepo

        issue_repo = ReviewIssueRepo(db)
        issue = await issue_repo.create(
            novel.id,
            run.id,
            {
                "issue_type": "continuity",
                "severity": "blocking",
                "resolution_mode": "needs_intent",
                "location": issue_location,
                "description": "连续性问题",
                "suggestion": "修复此处",
                "acceptance_blocking": True,
                "status": "open",
            },
        )
        await db.commit()

        return {
            "user_id": user.id,
            "novel_id": novel.id,
            "run_id": run.id,
            "version_id": version.id,
            "issue_id": issue.id,
        }


async def _get_auth_headers(client: AsyncClient, user_id: int):
    """Get auth headers for a user by user_id (must exist in DB)."""
    from app.core.security import create_token

    token = create_token({"user_id": user_id})
    return {"Authorization": f"Bearer {token}"}


async def _create_candidate_revision_db(novel_id: int, version_id: int, issue_id: int | None = None):
    """Create a candidate DraftRevision in DB."""
    async with async_session_factory() as db:
        from app.repositories.draft_version_repo import DraftVersionRepo

        dv_repo = DraftVersionRepo(db)
        version = await dv_repo.get(version_id, novel_id)
        content = version.content
        new_content = content[:6] + "修改后" + content[6:]
        patches = DraftVersionService._single_patch(content, new_content, "测试修改")

        candidate = await dv_repo.create_revision(
            novel_id,
            {
                "writing_run_id": version.writing_run_id,
                "draft_version_id": version.id,
                "sequence": 0,
                "source_type": "review_issue" if issue_id else "manual_edit",
                "source_id": issue_id,
                "base_revision_sequence": version.revision_sequence,
                "base_content_hash": DraftVersionService._hash_content(content),
                "base_content": content,
                "candidate_content": new_content,
                "patches_json": patches,
                "scope_json": {"type": "paragraph"},
                "diff_json": {"old": content, "new": new_content},
                "reason": "测试候选修订",
                "status": "candidate",
            },
        )
        await db.commit()
        return candidate.id


async def _setup_legacy_planning_candidate_db():
    """Create a pre-Phase-4 planning candidate with no DraftVersion link."""
    async with async_session_factory() as db:
        user = User(username="legacy_planning_candidate", hashed_password="x")
        db.add(user)
        await db.flush()
        novel = Novel(user_id=user.id, title="旧规划候选", genre="古风")
        db.add(novel)
        await db.flush()
        chapter_plan = ChapterPlan(novel_id=novel.id, position=1)
        db.add(chapter_plan)
        await db.flush()
        chapter_brief = ChapterBrief(novel_id=novel.id, chapter_plan_id=chapter_plan.id)
        db.add(chapter_brief)
        await db.flush()
        context_package = ContextPackage(novel_id=novel.id, chapter_brief_id=chapter_brief.id)
        db.add(context_package)
        await db.flush()
        run = WritingRun(
            novel_id=novel.id,
            chapter_brief_id=chapter_brief.id,
            context_package_id=context_package.id,
            draft_content="旧草稿正文",
            status="completed",
            planning_blocked=True,
        )
        db.add(run)
        await db.flush()
        candidate = DraftRevision(
            novel_id=novel.id,
            writing_run_id=run.id,
            source_type="planning_decision",
            base_content="旧草稿正文",
            candidate_content="修订后的草稿正文",
            scope_json={"type": "paragraph"},
            diff_json={"old": "旧草稿正文", "new": "修订后的草稿正文"},
            reason="旧规划决策",
            status="candidate",
        )
        db.add(candidate)
        await db.commit()
        return {"user_id": user.id, "novel_id": novel.id, "run_id": run.id, "revision_id": candidate.id}


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def override_modification_service():
    """Override get_modification_service with FakeModificationAgent for all tests.

    The override is a factory that receives the same sub-dependencies as the original
    (novel_id, current_user, db) and returns a ModificationService with FakeModificationAgent.
    """
    from app.main import app

    fake_agent = FakeModificationAgent()

    # The override must match the original dependency's parameter signature
    # so FastAPI can resolve sub-dependencies correctly.
    def _fake_modification_service(
        novel_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return ModificationService(db, current_user.id, novel_id, modification_agent=fake_agent)

    app.dependency_overrides[get_modification_service] = _fake_modification_service
    yield
    app.dependency_overrides.pop(get_modification_service, None)


# ── DraftVersion success paths ──────────────────────────────────────


@pytest.mark.asyncio
async def test_list_draft_versions(client):
    """GET /writing-runs/{run_id}/draft-versions returns version list."""
    info = await _setup_run_with_version_db()
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.get(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/draft-versions",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "message" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1
    assert body["data"][0]["id"] == info["version_id"]
    assert body["data"][0]["version"] == 1


@pytest.mark.asyncio
async def test_get_draft_version(client):
    """GET /draft-versions/{version_id} returns version detail."""
    info = await _setup_run_with_version_db()
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.get(
        f"/api/v1/novels/{info['novel_id']}/draft-versions/{info['version_id']}",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["id"] == info["version_id"]
    assert body["data"]["status"] == "draft"


@pytest.mark.asyncio
async def test_create_draft_version(client):
    """POST /writing-runs/{run_id}/draft-versions creates v2."""
    info = await _setup_run_with_version_db()
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/draft-versions",
        headers=headers,
        json={
            "based_on_version_id": info["version_id"],
            "change_reason": "调整节奏",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["version"] == 2
    assert body["data"]["status"] == "draft"


@pytest.mark.asyncio
async def test_restore_version_into_current(client):
    """POST /draft-versions/{version_id}/restore-into-current restores content."""
    info = await _setup_run_with_version_db()
    headers = await _get_auth_headers(client, info["user_id"])

    # Create v2 first
    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/draft-versions",
        headers=headers,
        json={
            "based_on_version_id": info["version_id"],
            "change_reason": "创建v2",
        },
    )
    v2_id = resp.json()["data"]["id"]

    # Make a manual revision on v2 to advance revision_sequence
    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/manual-revisions",
        headers=headers,
        json={
            "content": "这是一段修改后的正文内容，用于验证恢复功能。",
            "change_reason": "手动修订",
            "base_revision_sequence": 0,
        },
    )
    assert resp.status_code == 200

    # Restore v1 into current
    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/draft-versions/{info['version_id']}/restore-into-current",
        headers=headers,
        json={
            "base_revision_sequence": 1,
            "change_reason": "恢复v1",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["version"]["version"] == 2
    assert body["data"]["revision"]["source_type"] == "restore"


@pytest.mark.asyncio
async def test_create_manual_revision(client):
    """POST /writing-runs/{run_id}/manual-revisions saves revision."""
    info = await _setup_run_with_version_db()
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/manual-revisions",
        headers=headers,
        json={
            "content": "这是修改后的正文内容，与原文不同。",
            "change_reason": "补充角色动机",
            "base_revision_sequence": 0,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["version"]["revision_sequence"] == 1
    assert body["data"]["revision"]["source_type"] == "manual_edit"
    assert body["data"]["revision"]["status"] == "applied"


# ── ReviewIssue success paths ───────────────────────────────────────


@pytest.mark.asyncio
async def test_list_review_issues(client):
    """GET /writing-runs/{run_id}/review-issues returns issue list."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.get(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/review-issues",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1


@pytest.mark.asyncio
async def test_generate_repair_options(client):
    """POST /review-issues/{issue_id}/repair-options returns options."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/review-issues/{info['issue_id']}/repair-options",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1
    assert "option_index" in body["data"][0]
    assert "label" in body["data"][0]


@pytest.mark.asyncio
async def test_create_issue_revision(client):
    """POST /review-issues/{issue_id}/draft-revisions creates candidate revision."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])

    # First generate options
    await client.post(
        f"/api/v1/novels/{info['novel_id']}/review-issues/{info['issue_id']}/repair-options",
        headers=headers,
    )

    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/review-issues/{info['issue_id']}/draft-revisions",
        headers=headers,
        json={"option_index": 0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "candidate"
    assert body["data"]["source_type"] == "review_issue"


@pytest.mark.asyncio
async def test_ignore_review_issue(client):
    """PUT /review-issues/{issue_id}/ignore marks issue as ignored."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/review-issues/{info['issue_id']}/ignore",
        headers=headers,
        json={"reason": "作者确认无需修复"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "ignored"
    assert body["data"]["ignored_reason"] == "作者确认无需修复"


# ── DraftRevision success paths ─────────────────────────────────────


@pytest.mark.asyncio
async def test_list_draft_revisions(client):
    """GET /draft-versions/{version_id}/draft-revisions returns revision list."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])

    # Create a candidate revision via the issue endpoint
    await client.post(
        f"/api/v1/novels/{info['novel_id']}/review-issues/{info['issue_id']}/repair-options",
        headers=headers,
    )
    await client.post(
        f"/api/v1/novels/{info['novel_id']}/review-issues/{info['issue_id']}/draft-revisions",
        headers=headers,
        json={"option_index": 0},
    )

    resp = await client.get(
        f"/api/v1/novels/{info['novel_id']}/draft-versions/{info['version_id']}/draft-revisions",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1


@pytest.mark.asyncio
async def test_apply_draft_revision(client):
    """PUT /draft-revisions/{revision_id}/apply applies candidate revision."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])
    candidate_id = await _create_candidate_revision_db(
        info["novel_id"], info["version_id"], info["issue_id"]
    )

    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/draft-revisions/{candidate_id}/apply",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["revision"]["status"] == "applied"
    assert body["data"]["version"]["revision_sequence"] == 1


@pytest.mark.asyncio
async def test_apply_legacy_planning_candidate_via_revision_api(client):
    info = await _setup_legacy_planning_candidate_db()
    headers = await _get_auth_headers(client, info["user_id"])

    response = await client.put(
        f"/api/v1/novels/{info['novel_id']}/draft-revisions/{info['revision_id']}/apply",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["revision"]["status"] == "applied"
    async with async_session_factory() as db:
        run = await db.get(WritingRun, info["run_id"])
        assert run.draft_content == "修订后的草稿正文"
        assert run.planning_blocked is False


@pytest.mark.asyncio
async def test_reject_draft_revision(client):
    """PUT /draft-revisions/{revision_id}/reject rejects candidate revision."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])
    candidate_id = await _create_candidate_revision_db(
        info["novel_id"], info["version_id"], info["issue_id"]
    )

    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/draft-revisions/{candidate_id}/reject",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "rejected"


# ── Auth: missing authentication returns 401 ────────────────────────


@pytest.mark.asyncio
async def test_list_versions_no_auth_returns_401(client):
    """Missing auth returns 401."""
    resp = await client.get(
        "/api/v1/novels/1/writing-runs/1/draft-versions",
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_version_no_auth_returns_401(client):
    resp = await client.post(
        "/api/v1/novels/1/writing-runs/1/draft-versions",
        json={"based_on_version_id": 1, "change_reason": "test"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_apply_revision_no_auth_returns_401(client):
    resp = await client.put(
        "/api/v1/novels/1/draft-revisions/1/apply",
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_generate_options_no_auth_returns_401(client):
    resp = await client.post(
        "/api/v1/novels/1/review-issues/1/repair-options",
    )
    assert resp.status_code == 401


# ── Ownership: another user's resources return 404 ──────────────────


@pytest.mark.asyncio
async def test_get_version_other_user_returns_404(client):
    """Another user's version returns 404."""
    info = await _setup_run_with_version_db()

    # Register another user
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "other_user", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {resp.json()['data']['token']}"}

    resp = await client.get(
        f"/api/v1/novels/{info['novel_id']}/draft-versions/{info['version_id']}",
        headers=other_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_versions_other_user_novel_returns_404(client):
    """Another user's novel returns 404 for list versions."""
    info = await _setup_run_with_version_db()

    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "other_user2", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {resp.json()['data']['token']}"}

    resp = await client.get(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/draft-versions",
        headers=other_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ignore_issue_other_user_returns_404(client):
    """Another user's issue returns 404."""
    info = await _setup_run_with_issue_db()

    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "other_user3", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {resp.json()['data']['token']}"}

    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/review-issues/{info['issue_id']}/ignore",
        headers=other_headers,
        json={"reason": "测试"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_apply_revision_other_user_returns_404(client):
    """Another user's revision returns 404."""
    info = await _setup_run_with_issue_db()
    candidate_id = await _create_candidate_revision_db(
        info["novel_id"], info["version_id"], info["issue_id"]
    )

    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "other_user4", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {resp.json()['data']['token']}"}

    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/draft-revisions/{candidate_id}/apply",
        headers=other_headers,
    )
    assert resp.status_code == 404


# ── Version from another run cannot be used as base ─────────────────


@pytest.mark.asyncio
async def test_create_version_wrong_run_base_returns_400(client):
    """based_on_version_id from another run returns 400."""
    info = await _setup_run_with_version_db()

    # Create a second run in the same novel with its own DraftVersion
    async with async_session_factory() as db:
        cp = ChapterPlan(novel_id=info["novel_id"], position=2)
        db.add(cp)
        await db.flush()
        cb = ChapterBrief(novel_id=info["novel_id"], chapter_plan_id=cp.id)
        db.add(cb)
        await db.flush()
        ctx = ContextPackage(novel_id=info["novel_id"], chapter_brief_id=cb.id)
        db.add(ctx)
        await db.flush()
        run2 = WritingRun(
            novel_id=info["novel_id"],
            chapter_brief_id=cb.id,
            context_package_id=ctx.id,
            draft_content="第二个run的正文",
            status="completed",
        )
        db.add(run2)
        await db.flush()

        # Create initial version for run2
        svc = DraftVersionService(db, info["user_id"], info["novel_id"])
        await svc.ensure_initial_version(run2)
        await db.commit()
        run2_id = run2.id

    headers = await _get_auth_headers(client, info["user_id"])

    # Use v1 from run1 as base for run2
    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{run2_id}/draft-versions",
        headers=headers,
        json={
            "based_on_version_id": info["version_id"],
            "change_reason": "跨run测试",
        },
    )
    assert resp.status_code == 400
    assert "不属于" in resp.json()["message"]


# ── Stale revision sequence returns 400 ─────────────────────────────


@pytest.mark.asyncio
async def test_manual_revision_stale_sequence_returns_400(client):
    """Stale base_revision_sequence returns 400."""
    info = await _setup_run_with_version_db()
    headers = await _get_auth_headers(client, info["user_id"])

    # First revision advances sequence to 1
    await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/manual-revisions",
        headers=headers,
        json={
            "content": "第一次修订的内容，正文必须不同。",
            "change_reason": "第一次修订",
            "base_revision_sequence": 0,
        },
    )

    # Using stale base_revision_sequence=0 should fail
    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/manual-revisions",
        headers=headers,
        json={
            "content": "第二次修订的内容，仍然不同。",
            "change_reason": "第二次修订",
            "base_revision_sequence": 0,
        },
    )
    assert resp.status_code == 400
    assert "过期" in resp.json()["message"]


# ── Invalid body returns 422 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_version_missing_field_returns_422(client):
    """Missing required field in body returns 422."""
    info = await _setup_run_with_version_db()
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/draft-versions",
        headers=headers,
        json={"based_on_version_id": info["version_id"]},  # missing change_reason
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_revision_invalid_body_returns_422(client):
    """CreateRevisionRequest with neither option_index nor custom_intent returns 422."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/review-issues/{info['issue_id']}/draft-revisions",
        headers=headers,
        json={},  # neither option_index nor custom_intent
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ignore_issue_empty_reason_returns_422(client):
    """Empty reason in IgnoreIssueRequest returns 422."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/review-issues/{info['issue_id']}/ignore",
        headers=headers,
        json={"reason": ""},  # empty reason
    )
    assert resp.status_code == 422


# ── Expanded candidate without confirmation returns 400 ─────────────


@pytest.mark.asyncio
async def test_apply_expanded_scope_without_confirmation_returns_400(client):
    """Applying expanded_scope candidate without confirmation returns 400."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])
    candidate_id = await _create_candidate_revision_db(
        info["novel_id"], info["version_id"], info["issue_id"]
    )

    # Mark candidate as expanded_scope
    async with async_session_factory() as db:
        from app.models.plot_planning import DraftRevision as DR

        revision = await db.get(DR, candidate_id)
        revision.expanded_scope = True
        revision.expanded_scope_reason = "修改范围超出上下文窗口"
        await db.commit()

    # Apply without confirmation
    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/draft-revisions/{candidate_id}/apply",
        headers=headers,
    )
    assert resp.status_code == 400
    assert "确认扩大范围" in resp.json()["message"]


@pytest.mark.asyncio
async def test_apply_expanded_scope_with_confirmation_succeeds(client):
    """Applying expanded_scope candidate with confirmation succeeds."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])
    candidate_id = await _create_candidate_revision_db(
        info["novel_id"], info["version_id"], info["issue_id"]
    )

    # Mark candidate as expanded_scope
    async with async_session_factory() as db:
        from app.models.plot_planning import DraftRevision as DR

        revision = await db.get(DR, candidate_id)
        revision.expanded_scope = True
        revision.expanded_scope_reason = "修改范围超出上下文窗口"
        await db.commit()

    # Apply with confirmation
    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/draft-revisions/{candidate_id}/apply",
        headers=headers,
        json={"confirm_expanded_scope": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["revision"]["status"] == "applied"


# ── Accepted/discarded/locked writes return 400 ────────────────────


@pytest.mark.asyncio
async def test_create_version_on_accepted_run_returns_400(client):
    """Accepted run rejects create_new_version."""
    info = await _setup_run_with_version_db(run_status="accepted")
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/draft-versions",
        headers=headers,
        json={
            "based_on_version_id": info["version_id"],
            "change_reason": "测试",
        },
    )
    assert resp.status_code == 400
    assert "已接受" in resp.json()["message"]


@pytest.mark.asyncio
async def test_create_version_on_discarded_run_returns_400(client):
    """Discarded run rejects create_new_version."""
    info = await _setup_run_with_version_db(run_status="discarded")
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/draft-versions",
        headers=headers,
        json={
            "based_on_version_id": info["version_id"],
            "change_reason": "测试",
        },
    )
    assert resp.status_code == 400
    assert "已接受或丢弃" in resp.json()["message"]


@pytest.mark.asyncio
async def test_apply_revision_on_accepted_run_returns_400(client):
    """Accepted run rejects apply_revision."""
    async with async_session_factory() as db:
        user = User(username="accepted_apply_test", hashed_password="x")
        db.add(user)
        await db.flush()
        novel = Novel(
            title="已接受run测试", description="", genre="古风",
            style_guide="第三人称", user_id=user.id,
        )
        db.add(novel)
        await db.flush()
        cp = ChapterPlan(novel_id=novel.id, position=1)
        db.add(cp)
        await db.flush()
        cb = ChapterBrief(novel_id=novel.id, chapter_plan_id=cp.id)
        db.add(cb)
        await db.flush()
        ctx = ContextPackage(novel_id=novel.id, chapter_brief_id=cb.id)
        db.add(ctx)
        await db.flush()
        run = WritingRun(
            novel_id=novel.id, chapter_brief_id=cb.id,
            context_package_id=ctx.id, draft_content="测试", status="accepted",
        )
        db.add(run)
        await db.flush()
        svc = DraftVersionService(db, user.id, novel.id)
        version = await svc.ensure_initial_version(run)
        run_id = run.id
        version_id = version.id
        user_id = user.id
        novel_id = novel.id
        await db.commit()

    candidate_id = await _create_candidate_revision_db(novel_id, version_id)
    headers = await _get_auth_headers(client, user_id)

    resp = await client.put(
        f"/api/v1/novels/{novel_id}/draft-revisions/{candidate_id}/apply",
        headers=headers,
    )
    assert resp.status_code == 400
    assert "已接受或丢弃" in resp.json()["message"]


@pytest.mark.asyncio
async def test_apply_revision_on_locked_chapter_returns_400(client):
    """Locked chapter rejects apply_revision."""
    info = await _setup_run_with_issue_db()
    candidate_id = await _create_candidate_revision_db(
        info["novel_id"], info["version_id"], info["issue_id"]
    )

    # Create locked chapter and set as target
    async with async_session_factory() as db:
        chapter = Chapter(
            novel_id=info["novel_id"], title="已发布", content="事实", status="locked",
        )
        db.add(chapter)
        await db.flush()
        run = await db.get(WritingRun, info["run_id"])
        run.target_chapter_id = chapter.id
        await db.commit()

    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/draft-revisions/{candidate_id}/apply",
        headers=headers,
    )
    assert resp.status_code == 400
    assert "已发布" in resp.json()["message"]


@pytest.mark.asyncio
async def test_manual_revision_on_accepted_run_returns_400(client):
    """Accepted run rejects manual revision (no current draft version)."""
    info = await _setup_run_with_version_db(run_status="completed")

    # Accept the run via the writing API, which marks the version as "accepted"
    headers = await _get_auth_headers(client, info["user_id"])
    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/accept",
        headers=headers,
    )
    assert resp.status_code == 200

    # Now try a manual revision on the accepted run
    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/manual-revisions",
        headers=headers,
        json={
            "content": "修改后的内容",
            "change_reason": "测试",
            "base_revision_sequence": 0,
        },
    )
    # accepted run has no current draft version, so should 400
    assert resp.status_code == 400


# ── All success responses have code=0, message, typed data ──────────


@pytest.mark.asyncio
async def test_success_response_structure(client):
    """Verify all success responses have code=0, message, and typed data."""
    info = await _setup_run_with_version_db()
    headers = await _get_auth_headers(client, info["user_id"])

    # Test list versions
    resp = await client.get(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/draft-versions",
        headers=headers,
    )
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["message"], str)
    assert isinstance(body["data"], list)

    # Test get version
    resp = await client.get(
        f"/api/v1/novels/{info['novel_id']}/draft-versions/{info['version_id']}",
        headers=headers,
    )
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["message"], str)
    assert isinstance(body["data"], dict)
    # Verify typed fields exist
    assert "id" in body["data"]
    assert "version" in body["data"]
    assert "content" in body["data"]
    assert "status" in body["data"]


# ── Create issue revision with custom intent ─────────────────────────


@pytest.mark.asyncio
async def test_create_issue_revision_with_custom_intent(client):
    """POST /review-issues/{issue_id}/draft-revisions with custom_intent."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])

    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/review-issues/{info['issue_id']}/draft-revisions",
        headers=headers,
        json={"custom_intent": "请更加柔和地表达"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "candidate"


# ── Reject already-applied revision returns 400 ─────────────────────


@pytest.mark.asyncio
async def test_reject_applied_revision_returns_400(client):
    """Rejecting an already applied revision returns 400."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])
    candidate_id = await _create_candidate_revision_db(
        info["novel_id"], info["version_id"], info["issue_id"]
    )

    # Apply first
    await client.put(
        f"/api/v1/novels/{info['novel_id']}/draft-revisions/{candidate_id}/apply",
        headers=headers,
    )

    # Then try to reject
    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/draft-revisions/{candidate_id}/reject",
        headers=headers,
    )
    assert resp.status_code == 400
    assert "候选状态" in resp.json()["message"]


# ── Apply already-applied revision returns 400 ──────────────────────


@pytest.mark.asyncio
async def test_apply_already_applied_revision_returns_400(client):
    """Applying an already applied revision returns 400."""
    info = await _setup_run_with_issue_db()
    headers = await _get_auth_headers(client, info["user_id"])
    candidate_id = await _create_candidate_revision_db(
        info["novel_id"], info["version_id"], info["issue_id"]
    )

    # Apply first
    await client.put(
        f"/api/v1/novels/{info['novel_id']}/draft-revisions/{candidate_id}/apply",
        headers=headers,
    )

    # Try to apply again
    resp = await client.put(
        f"/api/v1/novels/{info['novel_id']}/draft-revisions/{candidate_id}/apply",
        headers=headers,
    )
    assert resp.status_code == 400
    assert "候选状态" in resp.json()["message"]


# ── Restore with stale sequence returns 400 ─────────────────────────


@pytest.mark.asyncio
async def test_restore_stale_sequence_returns_400(client):
    """Restore with stale base_revision_sequence returns 400."""
    info = await _setup_run_with_version_db()
    headers = await _get_auth_headers(client, info["user_id"])

    # Create v2
    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/draft-versions",
        headers=headers,
        json={
            "based_on_version_id": info["version_id"],
            "change_reason": "创建v2",
        },
    )
    v2_id = resp.json()["data"]["id"]

    # Make a manual revision on v2 to advance revision_sequence to 1
    await client.post(
        f"/api/v1/novels/{info['novel_id']}/writing-runs/{info['run_id']}/manual-revisions",
        headers=headers,
        json={
            "content": "这是一段修改后的正文内容，与原文不同。",
            "change_reason": "手动修订",
            "base_revision_sequence": 0,
        },
    )

    # Try to restore with stale base_revision_sequence=0 (should be 1)
    resp = await client.post(
        f"/api/v1/novels/{info['novel_id']}/draft-versions/{info['version_id']}/restore-into-current",
        headers=headers,
        json={
            "base_revision_sequence": 0,
            "change_reason": "恢复v1",
        },
    )
    assert resp.status_code == 400
    assert "过期" in resp.json()["message"]
