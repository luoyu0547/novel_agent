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


# ── Integration: one v1 after multiple internal rewrites ──────────────


class _CountingFakeGenerator:
    """Fake generator that counts generate_draft calls and returns
    incrementing content to simulate internal rewrites."""

    def __init__(self):
        self.generate_calls = 0

    async def generate_blueprint(self, novel_data, author_input):
        return {
            "core_promise": "test",
            "theme": "test",
            "main_conflict": "test",
            "character_arcs": "test",
            "world_rules": "test",
            "narrative_perspective": "test",
            "style_constraints": "test",
            "ending_direction": "test",
        }

    async def generate_chapter_plan(self, blueprint, novel_data):
        return {
            "chapter_title": "测试章节",
            "plot_task": "测试",
            "character_task": "测试",
            "information_task": "测试",
            "emotional_effect": "测试",
            "pacing": "测试",
            "foreshadowing_task": "测试",
        }

    async def generate_chapter_brief(self, chapter_plan, blueprint, length_contract):
        return {
            "writing_goal": "测试",
            "scenes": [],
            "participating_characters": "测试",
            "conflict_design": "测试",
            "information_control": "测试",
            "foreshadowing_handling": "测试",
            "writing_constraints": "测试",
            "acceptance_criteria": "测试",
        }

    async def generate_draft(self, context_package):
        self.generate_calls += 1
        return f"第{self.generate_calls}次生成的草稿正文" + "内容" * 500


class _RewritingFakeGateAgent:
    """Fake gate agent that forces two rewrites then passes."""

    def __init__(self, rewrites_before_pass=2):
        self._call_count = 0
        self._rewrites_before_pass = rewrites_before_pass

    async def check(self, draft, brief, context_package):
        self._call_count += 1
        from app.ai.quality_gate import AGENT_TYPES, CheckResult

        if self._call_count <= self._rewrites_before_pass:
            # Return a full_rewrite result to trigger rewrite_needed
            return [
                CheckResult(
                    passed=False,
                    issue_type="length",
                    severity="major",
                    resolution_mode="auto_fixable",
                    fix_strategy="full_rewrite",
                    fix_description="需要扩写",
                )
            ] + [
                CheckResult(passed=True, issue_type=t, severity="minor", resolution_mode="auto_fixable")
                for t in AGENT_TYPES
                if t != "length"
            ]
        return [
            CheckResult(passed=True, issue_type=t, severity="minor", resolution_mode="auto_fixable")
            for t in AGENT_TYPES
        ]


@pytest.mark.asyncio
async def test_one_v1_after_multiple_internal_rewrites(db):
    """After multiple quality-gate rewrites, exactly one v1 is created."""
    from app.services.writing_service import WritingService
    from app.repositories.draft_version_repo import DraftVersionRepo

    generator = _CountingFakeGenerator()
    gate_agent = _RewritingFakeGateAgent(rewrites_before_pass=2)

    # Build minimal FK chain
    user = User(username="rewrite_tester", hashed_password="x")
    db.add(user)
    await db.flush()

    novel = Novel(
        title="重写测试",
        description="",
        genre="古风",
        style_guide="第三人称",
        user_id=user.id,
    )
    db.add(novel)
    await db.flush()

    _, cb, ctx = await _make_fk_chain(db, novel.id)

    svc = WritingService(
        db=db,
        user_id=user.id,
        novel_id=novel.id,
        generator=generator,
        gate_agent=gate_agent,
    )
    run = await svc.create_writing_run(cb.id)

    assert run.status == "completed"
    assert generator.generate_calls >= 3  # initial + 2 rewrites

    versions = await DraftVersionRepo(db).list_by_run(run.id)
    assert len(versions) == 1
    assert versions[0].version == 1
    assert versions[0].revision_sequence == 0


# ── Integration: acceptance boundary tests ────────────────────────────


async def _setup_accepted_run(db, draft_content="初稿正文"):
    """Create a completed run with v1 DraftVersion, ready for accept testing."""
    run, user, novel = await _make_minimal_run(db, draft_content=draft_content)

    from app.services.draft_version_service import DraftVersionService
    dv_svc = DraftVersionService(db, user.id, novel.id)
    await dv_svc.ensure_initial_version(run)

    return run, user, novel


@pytest.mark.asyncio
async def test_candidate_revision_blocks_accept_even_with_force(db):
    """An open candidate DraftRevision blocks accept even with force_accept=true."""
    run, user, novel = await _setup_accepted_run(db)

    from app.repositories.draft_version_repo import DraftVersionRepo
    from app.services.draft_version_service import DraftVersionService
    from app.services.writing_service import WritingService
    from app.models.plot_planning import DraftRevision

    dv_repo = DraftVersionRepo(db)
    current = await dv_repo.get_current(run.id)

    # Create a candidate revision
    candidate = await dv_repo.create_revision(
        novel.id,
        {
            "writing_run_id": run.id,
            "draft_version_id": current.id,
            "sequence": 1,
            "source_type": "manual_edit",
            "base_revision_sequence": 0,
            "base_content_hash": "abc",
            "base_content": "旧",
            "candidate_content": "新",
            "patches_json": [],
            "diff_json": {},
            "scope_json": {"type": "manual"},
            "reason": "测试候选",
            "status": "candidate",
        },
    )
    await db.commit()

    svc = WritingService(db=db, user_id=user.id, novel_id=novel.id)
    from app.core.exceptions import AppException

    with pytest.raises(AppException, match="候选修订"):
        await svc.accept_writing_run(
            run.id, force_accept=True, force_reason="强制接受"
        )


@pytest.mark.asyncio
async def test_blocking_issue_blocks_normal_accept(db):
    """An open blocking ReviewIssue blocks normal accept."""
    run, user, novel = await _setup_accepted_run(db)

    from app.repositories.quality_gate_repo import ReviewIssueRepo
    from app.services.writing_service import WritingService
    from app.core.exceptions import AppException

    issue_repo = ReviewIssueRepo(db)
    await issue_repo.create(novel.id, run.id, {
        "issue_type": "continuity",
        "severity": "blocking",
        "resolution_mode": "needs_intent",
        "location": "段落3",
        "description": "连续性问题",
        "suggestion": "修复",
        "acceptance_blocking": True,
        "status": "open",
    })
    await db.commit()

    svc = WritingService(db=db, user_id=user.id, novel_id=novel.id)
    with pytest.raises(AppException, match="阻塞问题"):
        await svc.accept_writing_run(run.id)


@pytest.mark.asyncio
async def test_force_accept_without_reason_raises_error(db):
    """force_accept=true without a reason raises BadRequest."""
    run, user, novel = await _setup_accepted_run(db)

    from app.repositories.quality_gate_repo import ReviewIssueRepo
    from app.services.writing_service import WritingService
    from app.core.exceptions import BadRequest

    issue_repo = ReviewIssueRepo(db)
    await issue_repo.create(novel.id, run.id, {
        "issue_type": "continuity",
        "severity": "blocking",
        "resolution_mode": "needs_intent",
        "location": "段落3",
        "description": "连续性问题",
        "suggestion": "修复",
        "acceptance_blocking": True,
        "status": "open",
    })
    await db.commit()

    svc = WritingService(db=db, user_id=user.id, novel_id=novel.id)
    with pytest.raises(BadRequest, match="原因"):
        await svc.accept_writing_run(run.id, force_accept=True, force_reason=None)


@pytest.mark.asyncio
async def test_force_accept_with_reason_stores_override(db):
    """Force accept with a reason stores acceptance_override_reason on the version."""
    run, user, novel = await _setup_accepted_run(db)

    from app.repositories.quality_gate_repo import ReviewIssueRepo
    from app.repositories.draft_version_repo import DraftVersionRepo
    from app.services.writing_service import WritingService

    issue_repo = ReviewIssueRepo(db)
    await issue_repo.create(novel.id, run.id, {
        "issue_type": "continuity",
        "severity": "blocking",
        "resolution_mode": "needs_intent",
        "location": "段落3",
        "description": "连续性问题",
        "suggestion": "修复",
        "acceptance_blocking": True,
        "status": "open",
    })
    await db.commit()

    svc = WritingService(db=db, user_id=user.id, novel_id=novel.id)
    chapter, _ = await svc.accept_writing_run(
        run.id, force_accept=True, force_reason="作者确认可接受"
    )

    dv_repo = DraftVersionRepo(db)
    version = await dv_repo.get_current(run.id)
    # After accept, the version status is "accepted" so get_current won't find it.
    # Query directly.
    from sqlalchemy import select
    from app.models.draft_version import DraftVersion

    stmt = select(DraftVersion).where(DraftVersion.writing_run_id == run.id)
    result = await db.execute(stmt)
    v = result.scalar_one()
    assert v.acceptance_override_reason == "作者确认可接受"


@pytest.mark.asyncio
async def test_accept_writes_current_version_content_not_stale_run(db):
    """Accept writes current DraftVersion content, not stale WritingRun.draft_content."""
    run, user, novel = await _setup_accepted_run(db, draft_content="原始内容")

    from app.repositories.draft_version_repo import DraftVersionRepo
    from app.services.draft_version_service import DraftVersionService
    from app.services.writing_service import WritingService

    # Modify version content (simulating a manual revision)
    dv_repo = DraftVersionRepo(db)
    current = await dv_repo.get_current(run.id)
    current.content = "修订后的内容"
    run.draft_content = "旧的内容"  # Simulate stale run content
    await db.commit()

    svc = WritingService(db=db, user_id=user.id, novel_id=novel.id)
    chapter, _ = await svc.accept_writing_run(run.id)

    assert chapter.content == "修订后的内容"


@pytest.mark.asyncio
async def test_accepted_version_becomes_frozen_with_chapter_id(db):
    """Accepted version becomes frozen with chapter_id."""
    run, user, novel = await _setup_accepted_run(db)

    from app.repositories.draft_version_repo import DraftVersionRepo
    from app.services.writing_service import WritingService

    svc = WritingService(db=db, user_id=user.id, novel_id=novel.id)
    chapter, _ = await svc.accept_writing_run(run.id)

    dv_repo = DraftVersionRepo(db)
    # After accept, version status is "accepted" — query directly
    from sqlalchemy import select
    from app.models.draft_version import DraftVersion

    stmt = select(DraftVersion).where(DraftVersion.writing_run_id == run.id)
    result = await db.execute(stmt)
    v = result.scalar_one()
    assert v.status == "accepted"
    assert v.chapter_id == chapter.id


@pytest.mark.asyncio
async def test_discard_marks_current_version_rejected(db):
    """Discard marks the current version as rejected."""
    run, user, novel = await _setup_accepted_run(db)

    from app.services.writing_service import WritingService
    from sqlalchemy import select
    from app.models.draft_version import DraftVersion

    svc = WritingService(db=db, user_id=user.id, novel_id=novel.id)
    await svc.discard_writing_run(run.id)

    stmt = select(DraftVersion).where(DraftVersion.writing_run_id == run.id)
    result = await db.execute(stmt)
    v = result.scalar_one()
    assert v.status == "rejected"


@pytest.mark.asyncio
async def test_accepted_run_rejects_phase4_writes(db):
    """Accepted runs reject further Phase 4 writes (create_new_version)."""
    run, user, novel = await _setup_accepted_run(db)

    from app.services.writing_service import WritingService
    from app.services.draft_version_service import DraftVersionService
    from app.core.exceptions import BadRequest

    svc = WritingService(db=db, user_id=user.id, novel_id=novel.id)
    chapter, _ = await svc.accept_writing_run(run.id)

    dv_svc = DraftVersionService(db, user.id, novel.id)
    from sqlalchemy import select
    from app.models.draft_version import DraftVersion

    stmt = select(DraftVersion).where(DraftVersion.writing_run_id == run.id)
    result = await db.execute(stmt)
    v = result.scalar_one()

    with pytest.raises(BadRequest, match="已接受"):
        await dv_svc.create_new_version(run.id, v.id, "新版本")


@pytest.mark.asyncio
async def test_discarded_run_rejects_phase4_writes(db):
    """Discarded runs reject further Phase 4 writes (create_new_version)."""
    run, user, novel = await _setup_accepted_run(db)

    from app.services.writing_service import WritingService
    from app.services.draft_version_service import DraftVersionService
    from app.core.exceptions import BadRequest

    svc = WritingService(db=db, user_id=user.id, novel_id=novel.id)
    await svc.discard_writing_run(run.id)

    dv_svc = DraftVersionService(db, user.id, novel.id)
    from sqlalchemy import select
    from app.models.draft_version import DraftVersion

    stmt = select(DraftVersion).where(DraftVersion.writing_run_id == run.id)
    result = await db.execute(stmt)
    v = result.scalar_one()

    with pytest.raises(BadRequest, match="已接受或丢弃"):
        await dv_svc.create_new_version(run.id, v.id, "新版本")
