"""Phase 4 DraftVersion 生命周期测试。

覆盖 enforce_initial_version、save_manual_revision、create_new_version、
restore_into_current、reject_revision、mark_run_rejected 及其负面场景。
"""

import pytest

from app.core.exceptions import BadRequest, NotFound
from app.models.draft_version import DraftVersion
from app.models.novel import Chapter, Novel
from app.models.plot_planning import DraftRevision
from app.models.user import User
from app.models.writing import ChapterBrief, ChapterPlan, ContextPackage, WritingRun
from app.services.draft_version_service import DraftVersionService


# ── Fixture helpers ────────────────────────────────────────────────


async def _make_fk_chain(db, novel_id: int):
    """创建 ChapterPlan → ChapterBrief → ContextPackage 链。"""
    cp = ChapterPlan(novel_id=novel_id, position=1)
    db.add(cp)
    await db.flush()
    cb = ChapterBrief(novel_id=novel_id, chapter_plan_id=cp.id)
    db.add(cb)
    await db.flush()
    ctx = ContextPackage(novel_id=novel_id, chapter_brief_id=cb.id)
    db.add(ctx)
    await db.flush()
    return cp, cb, ctx


async def _make_minimal_run(
    db, draft_content: str = "初稿正文", status: str = "completed"
) -> tuple[WritingRun, User, Novel]:
    """创建完整的 FK 链并返回 (run, user, novel)。"""
    user = User(username="author", hashed_password="x")
    db.add(user)
    await db.flush()

    novel = Novel(
        title="测试小说",
        description="",
        genre="古风",
        style_guide="第三人称",
        user_id=user.id,
    )
    db.add(novel)
    await db.flush()

    _, cb, ctx = await _make_fk_chain(db, novel.id)

    run = WritingRun(
        novel_id=novel.id,
        chapter_brief_id=cb.id,
        context_package_id=ctx.id,
        draft_content=draft_content,
        status=status,
    )
    db.add(run)
    await db.flush()
    return run, user, novel


# ── Happy path: ensure_initial_version ──────────────────────────────


@pytest.mark.asyncio
async def test_ensure_initial_version_creates_v1(db):
    """ensure_initial_version 创建 v1，version=1, status=draft。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)

    assert v1.version == 1
    assert v1.status == "draft"
    assert v1.content == "初稿正文"
    assert v1.revision_sequence == 0


@pytest.mark.asyncio
async def test_ensure_initial_version_idempotent(db):
    """ensure_initial_version 多次调用返回同一版本。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)
    same_v1 = await service.ensure_initial_version(run)

    assert same_v1.id == v1.id


@pytest.mark.asyncio
async def test_ensure_initial_version_fails_empty_content(db):
    """ensure_initial_version 对空 draft_content 抛出 BadRequest。"""
    run, _, novel = await _make_minimal_run(db, draft_content="")

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    with pytest.raises(BadRequest, match="没有草稿内容"):
        await service.ensure_initial_version(run)


# ── save_manual_revision ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_manual_revision_creates_applied(db):
    """save_manual_revision 创建 applied DraftRevision, revision_sequence += 1。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)

    new_content = "初稿正文，补充角色动机。"
    version, revision = await service.save_manual_revision(
        run.id,
        content=new_content,
        change_reason="补充角色动机",
        base_revision_sequence=0,
    )

    assert version.version == 1
    assert version.revision_sequence == 1
    assert version.content == new_content
    assert revision.source_type == "manual_edit"
    assert revision.status == "applied"
    assert revision.sequence == 1
    assert revision.draft_version_id == version.id
    assert len(revision.patches_json) == 1


# ── create_new_version ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_new_version_creates_v2_archives_v1(db):
    """create_new_version 创建 v2(draft)，v1 变为 archived。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)

    v2 = await service.create_new_version(run.id, v1.id, "重新调整节奏")
    assert v2.version == 2
    assert v2.status == "draft"
    assert v2.revision_sequence == 0
    assert v2.content == v1.content

    # v1 应被归档
    v1_loaded = await service.get_version(v1.id)
    assert v1_loaded.status == "archived"

    # 确认 list_versions 返回 [2, 1]
    versions = await service.list_versions(run.id)
    assert [v.version for v in versions] == [2, 1]


# ── restore_into_current ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_restore_into_current_restores_content(db):
    """restore_into_current 恢复到历史版本内容，不创建新 version。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)

    # 创建 v2（保留 v1 的原始内容 "初稿正文"）
    v2 = await service.create_new_version(run.id, v1.id, "新建 v2")

    # 修改 v2 内容 → revision_sequence=1
    await service.save_manual_revision(
        run.id, "修订后的内容。", "修订", base_revision_sequence=0,
    )

    # 从 v2 恢复到 v1 的历史内容
    version, revision = await service.restore_into_current(
        v1.id, base_revision_sequence=1, change_reason="恢复初始版本",
    )

    assert version.version == 2
    assert version.revision_sequence == 2
    assert version.content == "初稿正文"
    assert revision.source_type == "restore"
    assert revision.source_id == v1.id
    assert revision.status == "applied"
    assert revision.sequence == 2


# ── reject_revision & mark_run_rejected ─────────────────────────────


@pytest.mark.asyncio
async def test_reject_revision_rejects_candidate(db):
    """reject_revision 将 candidate revision 标记为 rejected。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)

    # save_manual_revision 直接创建 applied 状态，我们需要一个 candidate 状态的 revision
    # 可以直接通过 repo 创建一个 candidate revision
    from app.repositories.draft_version_repo import DraftVersionRepo

    repo = DraftVersionRepo(db)
    candidate = await repo.create_revision(
        novel.id,
        {
            "writing_run_id": run.id,
            "draft_version_id": v1.id,
            "sequence": 99,
            "source_type": "manual_edit",
            "base_revision_sequence": 0,
            "base_content_hash": "",
            "base_content": "旧",
            "candidate_content": "新",
            "patches_json": [],
            "diff_json": {},
            "scope_json": {"type": "manual"},
            "reason": "测试",
            "status": "candidate",
        },
    )
    await db.flush()

    rejected = await service.reject_revision(candidate.id)
    assert rejected.status == "rejected"


@pytest.mark.asyncio
async def test_reject_revision_already_applied_fails(db):
    """只能拒绝候选状态的修订。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)

    _, rev = await service.save_manual_revision(
        run.id, "修订内容", "测试", base_revision_sequence=0,
    )

    with pytest.raises(BadRequest, match="只能拒绝候选"):
        await service.reject_revision(rev.id)


@pytest.mark.asyncio
async def test_mark_run_rejected_sets_version_status(db):
    """mark_run_rejected 将当前 draft 版本标记为 rejected。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    await service.ensure_initial_version(run)

    rejected = await service.mark_run_rejected(run)
    assert rejected is not None
    assert rejected.status == "rejected"


@pytest.mark.asyncio
async def test_mark_run_rejected_no_current_version(db):
    """mark_run_rejected 在无当前版本时返回 None。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    result = await service.mark_run_rejected(run)
    assert result is None


# ── Negative: stale base_revision_sequence ─────────────────────────


@pytest.mark.asyncio
async def test_save_manual_revision_stale_base_sequence(db):
    """save_manual_revision 在 base_revision_sequence 过期时拒绝。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    await service.ensure_initial_version(run)

    # 第一次修订 → revision_sequence=1
    await service.save_manual_revision(
        run.id, "第一次修订", "修订1", base_revision_sequence=0,
    )

    # 第二次修订使用旧的 base=0 → 过期
    with pytest.raises(BadRequest, match="已过期"):
        await service.save_manual_revision(
            run.id, "第二次修订", "修订2", base_revision_sequence=0,
        )


# ── Negative: accepted / discarded runs ──────────────────────────────


@pytest.mark.asyncio
async def test_create_new_version_on_accepted_run_fails(db):
    """accepted 状态的 run 不能创建新版本。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)

    run.status = "accepted"
    await db.flush()

    with pytest.raises(BadRequest, match="已接受"):
        await service.create_new_version(run.id, v1.id, "测试")


@pytest.mark.asyncio
async def test_create_new_version_on_discarded_run_fails(db):
    """discarded 状态的 run 不能创建新版本。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)

    run.status = "discarded"
    await db.flush()

    with pytest.raises(BadRequest, match="已接受或丢弃"):
        await service.create_new_version(run.id, v1.id, "测试")


# ── Negative: locked target chapter ─────────────────────────────────


@pytest.mark.asyncio
async def test_create_new_version_locked_chapter_fails(db):
    """target_chapter_id 指向 locked 章节时拒绝。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)

    chapter = Chapter(
        novel_id=novel.id, title="锁定章", content="...", status="locked",
    )
    db.add(chapter)
    await db.flush()

    run.target_chapter_id = chapter.id
    await db.flush()

    with pytest.raises(BadRequest, match="已发布"):
        await service.create_new_version(run.id, v1.id, "测试")


# ── Negative: source version from another run ────────────────────────


@pytest.mark.asyncio
async def test_create_new_version_wrong_source_run_fails(db):
    """based_on_version_id 属于不同 run 时拒绝。"""
    run1, _, novel = await _make_minimal_run(db)
    # 第二个 run（同一 novel）
    _, cb2, ctx2 = await _make_fk_chain(db, novel.id)
    run2 = WritingRun(
        novel_id=novel.id,
        chapter_brief_id=cb2.id,
        context_package_id=ctx2.id,
        draft_content="第二 run 正文",
        status="completed",
    )
    db.add(run2)
    await db.flush()

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run1)

    # v1 属于 run1，不能用于 run2
    with pytest.raises(BadRequest, match="不属于"):
        await service.create_new_version(run2.id, v1.id, "测试")


# ── Negative: source version from another novel ──────────────────────


@pytest.mark.asyncio
async def test_create_new_version_wrong_source_novel_fails(db):
    """based_on_version_id 属于不同 novel 时返回 NotFound（novel_id 过滤）。"""
    run1, _, novel1 = await _make_minimal_run(db)
    # 第二个用户 + 小说 + run
    user2 = User(username="author2", hashed_password="x")
    db.add(user2)
    await db.flush()
    novel2 = Novel(
        title="第二本小说",
        description="",
        genre="现代",
        style_guide="第一人称",
        user_id=user2.id,
    )
    db.add(novel2)
    await db.flush()
    _, cb2, ctx2 = await _make_fk_chain(db, novel2.id)
    run2 = WritingRun(
        novel_id=novel2.id,
        chapter_brief_id=cb2.id,
        context_package_id=ctx2.id,
        draft_content="小说2正文",
        status="completed",
    )
    db.add(run2)
    await db.flush()

    service1 = DraftVersionService(db, novel1.user_id, novel1.id)
    v1 = await service1.ensure_initial_version(run1)

    # v1 属于 novel1，run2 属于 novel2 → _get_owned_run 会 NotFound
    with pytest.raises(NotFound):
        await service1.create_new_version(run2.id, v1.id, "测试")


# ── Negative: no current draft version ──────────────────────────────


@pytest.mark.asyncio
async def test_create_new_version_no_current_draft_fails(db):
    """当前没有 draft 版本时不能创建新版本。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)

    # 手动归档 v1
    v1.status = "archived"
    await db.flush()

    with pytest.raises(BadRequest, match="没有草稿版本"):
        await service.create_new_version(run.id, v1.id, "测试")


# ── Negative: identical content ─────────────────────────────────────


@pytest.mark.asyncio
async def test_save_manual_revision_identical_content_fails(db):
    """save_manual_revision 在正文无变化时拒绝。"""
    run, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    v1 = await service.ensure_initial_version(run)

    with pytest.raises(BadRequest, match="没有变化"):
        await service.save_manual_revision(
            run.id, v1.content, "无变化", base_revision_sequence=0,
        )


# ── Negative: missing revision ──────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_revision_not_found(db):
    """reject_revision 对不存在的 revision_id 返回 NotFound。"""
    _, _, novel = await _make_minimal_run(db)

    from app.services.draft_version_service import DraftVersionService

    service = DraftVersionService(db, novel.user_id, novel.id)
    with pytest.raises(NotFound):
        await service.reject_revision(99999)
