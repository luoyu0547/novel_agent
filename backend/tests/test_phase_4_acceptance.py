"""Phase 4 辅助修订——完整验收测试。

执行 14 步确定性场景，验证 DraftVersion 生命周期、候选修订、
手动修订、版本恢复、接受/发布和锁定后写入拒绝的完整路径。

使用 FakeWritingGenerator、FakeQualityGateAgent、FakeModificationAgent，
不调用真实 DeepSeek API。
"""

import pytest

from app.ai.modification import (
    FakeModificationAgent,
    ModificationOutput,
    RepairOption,
    RepairOptionsOutput,
    RevisionPatch,
)
from app.ai.quality_gate import AGENT_TYPES, CheckResult, FakeQualityGateAgent
from app.ai.writer import FakeWritingGenerator
from app.core.exceptions import BadRequest, NotFound
from app.models.draft_version import DraftVersion
from app.models.novel import Chapter, Novel
from app.models.plot_planning import DraftRevision
from app.models.quality_gate import ReviewIssue
from app.models.user import User
from app.models.writing import ChapterBrief, ChapterPlan, ContextPackage, WritingRun
from app.repositories.draft_version_repo import DraftVersionRepo
from app.repositories.quality_gate_repo import ReviewIssueRepo
from app.services.draft_version_service import DraftVersionService
from app.services.modification_service import ModificationService
from app.services.writing_service import WritingService


# ── Fixture helpers ────────────────────────────────────────────────


async def _make_fk_chain(db, novel_id: int):
    """创建 ChapterPlan -> ChapterBrief -> ContextPackage 链。"""
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


class _CountingFakeGenerator(FakeWritingGenerator):
    """Fake generator that counts generate_draft calls and returns
    incrementing content to simulate internal rewrites."""

    def __init__(self):
        super().__init__()
        self.generate_calls = 0

    async def generate_draft(self, context_package):
        self.generate_calls += 1
        return f"第{self.generate_calls}次生成的草稿正文" + "内容" * 500


class _RewritingFakeGateAgent(FakeQualityGateAgent):
    """Fake gate agent that forces two rewrites then passes."""

    def __init__(self, rewrites_before_pass=2):
        self._call_count = 0
        self._rewrites_before_pass = rewrites_before_pass

    async def check(self, draft, brief, context_package):
        self._call_count += 1
        if self._call_count <= self._rewrites_before_pass:
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


# ── Full acceptance test ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_phase4_full_acceptance_path(db):
    """14-step acceptance test: complete Phase 4 lifecycle with fakes."""

    # ── Step 1: Generate initial draft with expansion and two quality-gate rewrites ──
    generator = _CountingFakeGenerator()
    gate_agent = _RewritingFakeGateAgent(rewrites_before_pass=2)

    user = User(username="acceptance_tester", hashed_password="x")
    db.add(user)
    await db.flush()

    novel = Novel(
        title="验收测试小说",
        description="",
        genre="古风",
        style_guide="第三人称",
        user_id=user.id,
    )
    db.add(novel)
    await db.flush()

    _, cb, ctx = await _make_fk_chain(db, novel.id)

    # Use a fake extraction service to avoid real AI calls during accept
    from app.ai.service import FakeExtractionService

    svc = WritingService(
        db=db,
        user_id=user.id,
        novel_id=novel.id,
        generator=generator,
        gate_agent=gate_agent,
        extraction_service=FakeExtractionService(),
    )
    run = await svc.create_writing_run(cb.id)

    assert run.status == "completed"
    assert generator.generate_calls >= 3  # initial + 2 rewrites

    # ── Step 2: Assert exactly one DraftVersion v1 and revision_sequence 0 ──
    dv_repo = DraftVersionRepo(db)
    versions = await dv_repo.list_by_run(run.id)
    assert len(versions) == 1
    v1 = versions[0]
    assert v1.version == 1
    assert v1.revision_sequence == 0
    assert v1.status == "draft"

    # ── Step 3: Review and create an open ReviewIssue ──
    issue_repo = ReviewIssueRepo(db)
    issue = await issue_repo.create(
        novel.id,
        run.id,
        {
            "issue_type": "continuity",
            "severity": "blocking",
            "resolution_mode": "needs_intent",
            "location": "草稿正文",
            "description": "连续性问题：时间线矛盾",
            "suggestion": "统一日期描述",
            "acceptance_blocking": True,
            "status": "open",
        },
    )
    await db.commit()

    assert issue.status == "open"
    assert issue.acceptance_blocking is True

    # ── Step 4: Generate multiple repair directions ──
    options_output = RepairOptionsOutput(
        options=[
            RepairOption(
                label="修改措辞",
                summary="修改问题段落的措辞以消除矛盾",
                action="replace_text",
                expected_effect="消除连续性问题",
                estimated_scope={"type": "paragraph", "chars": 50},
                recommended=True,
                recommendation_reason="最小影响范围",
            ),
            RepairOption(
                label="补充过渡",
                summary="补充一段过渡文字使时间线合理",
                action="add_transition",
                expected_effect="时间线连贯",
                estimated_scope={"type": "paragraph", "chars": 100},
            ),
        ],
    )
    mod_agent = FakeModificationAgent(options_output=options_output)
    mod_svc = ModificationService(db, user.id, novel.id, modification_agent=mod_agent)

    options = await mod_svc.generate_options(issue.id)
    assert len(options) == 2

    # ── Step 5: Generate candidate A and assert v1 content unchanged ──
    # Build a modification output that produces a real change
    v1_content = v1.content
    # Create a simple patch: replace first 6 chars with something else
    patch_a = RevisionPatch(
        start_offset=0,
        end_offset=min(len(v1_content), 6),
        original_text=v1_content[: min(len(v1_content), 6)],
        replacement_text="候选A修改",
        reason="修复连续性问题",
    )
    candidate_a_content = "候选A修改" + v1_content[min(len(v1_content), 6):]

    mod_output_a = ModificationOutput(
        candidate_content=candidate_a_content,
        patches=[patch_a],
        diff={"old": v1_content, "new": candidate_a_content},
        change_reason="修复连续性问题-候选A",
        scope={"type": "paragraph"},
    )
    mod_agent._modification_output = mod_output_a

    candidate_a = await mod_svc.create_revision(issue.id, option_index=0)
    assert candidate_a.status == "candidate"

    # v1 content must be unchanged
    await db.refresh(v1)
    assert v1.content == v1_content
    assert v1.revision_sequence == 0

    # ── Step 6: Reject candidate A and assert issue remains open ──
    dv_svc = DraftVersionService(db, user.id, novel.id)
    rejected_a = await dv_svc.reject_revision(candidate_a.id)
    assert rejected_a.status == "rejected"

    await db.refresh(issue)
    assert issue.status == "open"

    # v1 content still unchanged
    await db.refresh(v1)
    assert v1.content == v1_content

    # ── Step 7: Generate/apply candidate B; assert R1 applied and version still v1 ──
    # Build candidate B with a different change
    patch_b = RevisionPatch(
        start_offset=0,
        end_offset=min(len(v1_content), 6),
        original_text=v1_content[: min(len(v1_content), 6)],
        replacement_text="候选B修改",
        reason="修复连续性问题-候选B",
    )
    candidate_b_content = "候选B修改" + v1_content[min(len(v1_content), 6):]

    mod_output_b = ModificationOutput(
        candidate_content=candidate_b_content,
        patches=[patch_b],
        diff={"old": v1_content, "new": candidate_b_content},
        change_reason="修复连续性问题-候选B",
        scope={"type": "paragraph"},
    )
    mod_agent._modification_output = mod_output_b

    candidate_b = await mod_svc.create_revision(issue.id, option_index=1)
    assert candidate_b.status == "candidate"

    # Apply candidate B
    updated_v1, applied_b = await dv_svc.apply_revision(candidate_b.id)
    assert applied_b.status == "applied"
    assert updated_v1.version == 1  # version number unchanged
    assert updated_v1.revision_sequence == 1  # R1 applied
    assert updated_v1.content == candidate_b_content

    # Issue should be resolved now
    await db.refresh(issue)
    assert issue.status == "resolved"

    # ── Step 8: Manually save content; assert R2 applied and version still v1 ──
    manual_content = updated_v1.content + "，补充角色动机。"
    updated_v1_r2, revision_r2 = await dv_svc.save_manual_revision(
        run.id,
        content=manual_content,
        change_reason="补充角色动机",
        base_revision_sequence=1,
    )
    assert updated_v1_r2.version == 1  # still v1
    assert updated_v1_r2.revision_sequence == 2  # R2 applied
    assert updated_v1_r2.content == manual_content
    assert revision_r2.source_type == "manual_edit"
    assert revision_r2.status == "applied"

    # ── Step 9: Explicitly create a new version based on v1; assert exactly v2 is current ──
    v2 = await dv_svc.create_new_version(run.id, v1.id, "重新调整节奏")
    assert v2.version == 2
    assert v2.status == "draft"
    assert v2.revision_sequence == 0

    # v1 should be archived
    v1_loaded = await dv_svc.get_version(v1.id)
    assert v1_loaded.status == "archived"

    # Exactly v2 is current
    current = await dv_repo.get_current(run.id)
    assert current is not None
    assert current.version == 2

    # ── Step 10: Restore v1 into v2; assert a restore revision exists and version remains v2 ──
    # v2 content should be the same as v1's final content (from create_new_version)
    # Now restore v1's original content into v2
    version_v2, restore_revision = await dv_svc.restore_into_current(
        v1.id,
        base_revision_sequence=0,
        change_reason="恢复初始版本内容",
    )
    assert version_v2.version == 2  # still v2
    assert version_v2.revision_sequence == 1  # restore increments sequence
    assert restore_revision.source_type == "restore"
    assert restore_revision.source_id == v1.id
    assert restore_revision.status == "applied"

    # ── Step 11: Resolve/ignore remaining blocking issues ──
    # Create another blocking issue to test ignore
    issue2 = await issue_repo.create(
        novel.id,
        run.id,
        {
            "issue_type": "style",
            "severity": "blocking",
            "resolution_mode": "needs_intent",
            "location": "段落5",
            "description": "风格不一致",
            "suggestion": "统一叙述风格",
            "acceptance_blocking": True,
            "status": "open",
        },
    )
    await db.commit()

    # Ignore the blocking issue
    ignored = await mod_svc.ignore_issue(issue2.id, "作者确认风格偏好")
    assert ignored.status == "ignored"

    # ── Step 12: Accept v2; assert Chapter content equals v2, version accepted ──
    # Need to use WritingService.accept_writing_run which uses FakeExtractionService
    writing_svc = WritingService(
        db=db,
        user_id=user.id,
        novel_id=novel.id,
        generator=generator,
        gate_agent=gate_agent,
        extraction_service=FakeExtractionService(),
    )
    chapter, extraction_result = await writing_svc.accept_writing_run(run.id)

    # Chapter content should equal current DraftVersion (v2) content
    current_v2 = await dv_repo.get(run.id, novel.id)
    # After accept, get_current won't find it (status=accepted), query directly
    from sqlalchemy import select

    stmt = select(DraftVersion).where(
        DraftVersion.writing_run_id == run.id,
        DraftVersion.version == 2,
    )
    result = await db.execute(stmt)
    v2_accepted = result.scalar_one()
    assert v2_accepted.status == "accepted"
    assert chapter.content == v2_accepted.content

    # Extraction was called (FakeExtractionService returns data)
    assert extraction_result is not None

    # ── Step 13: Publish Chapter to locked ──
    chapter.status = "locked"
    await db.flush()

    assert chapter.status == "locked"

    # ── Step 14: Assert create version, restore, manual save and candidate apply all fail ──

    # 14a. Create new version on accepted run fails
    with pytest.raises(BadRequest, match="已接受"):
        await dv_svc.create_new_version(run.id, v2_accepted.id, "尝试创建v3")

    # 14b. Restore into current fails (chapter is locked)
    with pytest.raises(BadRequest, match="已发布"):
        await dv_svc.restore_into_current(
            v1.id,
            base_revision_sequence=1,
            change_reason="尝试恢复",
        )

    # 14c. Manual save fails (chapter is locked)
    with pytest.raises(BadRequest, match="已发布"):
        await dv_svc.save_manual_revision(
            run.id,
            content="尝试手动保存",
            change_reason="尝试",
            base_revision_sequence=1,
        )

    # 14d. Candidate apply fails (version is accepted, not draft)
    candidate_stale = await dv_repo.create_revision(
        novel.id,
        {
            "writing_run_id": run.id,
            "draft_version_id": v2_accepted.id,
            "sequence": 99,
            "source_type": "manual_edit",
            "base_revision_sequence": 0,
            "base_content_hash": "abc",
            "base_content": "旧",
            "candidate_content": "新",
            "patches_json": [],
            "diff_json": {},
            "scope_json": {"type": "manual"},
            "reason": "测试锁定后应用",
            "status": "candidate",
        },
    )
    await db.commit()

    with pytest.raises(BadRequest, match="draft 状态"):
        await dv_svc.apply_revision(candidate_stale.id)
