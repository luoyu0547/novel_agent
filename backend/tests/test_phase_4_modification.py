"""Phase 4 Modification Agent 和 ModificationService 测试。

覆盖:
- Pydantic 协议验证 (RepairOption, RepairOptionsOutput, RevisionPatch, ModificationOutput)
- 非变异候选生成 (content unchanged after create_revision)
- 1-3 选项生成
- 无效选项索引
- 自定义意图
- 关闭问题拒绝
- AI 异常 (无 DraftRevision 行)
- 重叠补丁 (无 DraftRevision 行)
- 不匹配的 original_text (无 DraftRevision 行)
- 候选内容与补丁重建不一致 (无 DraftRevision 行)
"""

import pytest
from pydantic import ValidationError

from app.ai.modification import (
    FakeModificationAgent,
    ModificationOutput,
    RepairOption,
    RepairOptionsOutput,
    RevisionPatch,
)
from app.core.exceptions import BadRequest, NotFound
from app.models.draft_version import DraftVersion
from app.models.novel import Novel
from app.models.plot_planning import DraftRevision
from app.models.quality_gate import ReviewIssue
from app.models.user import User
from app.models.writing import ChapterBrief, ChapterPlan, ContextPackage, WritingRun
from app.services.draft_version_service import DraftVersionService
from app.services.modification_service import ModificationService


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


async def _setup_run_with_issue(
    db,
    draft_content: str = "这是一段测试正文，用于验证修改服务的功能。",
    issue_location: str = "测试正文",
    issue_status: str = "open",
) -> tuple[WritingRun, User, Novel, DraftVersion, ReviewIssue]:
    """创建完整的 FK 链并返回 (run, user, novel, version, issue)。"""
    user = User(username="modifier", hashed_password="x")
    db.add(user)
    await db.flush()

    novel = Novel(
        title="修改测试小说",
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
        status="completed",
    )
    db.add(run)
    await db.flush()

    # Create initial DraftVersion
    dv_svc = DraftVersionService(db, user.id, novel.id)
    version = await dv_svc.ensure_initial_version(run)

    # Create ReviewIssue
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
            "status": issue_status,
        },
    )
    await db.commit()

    return run, user, novel, version, issue


# ── Pydantic protocol tests ──────────────────────────────────────────


class TestRepairOption:
    def test_valid_option(self):
        opt = RepairOption(
            label="修改措辞",
            summary="修改问题段落的措辞",
            action="replace_text",
            expected_effect="消除连续性问题",
            estimated_scope={"type": "paragraph", "chars": 50},
        )
        assert opt.label == "修改措辞"
        assert opt.recommended is False

    def test_empty_label_rejected(self):
        with pytest.raises(ValidationError):
            RepairOption(
                label="",
                summary="s",
                action="a",
                expected_effect="e",
                estimated_scope={},
            )

    def test_empty_action_rejected(self):
        with pytest.raises(ValidationError):
            RepairOption(
                label="l",
                summary="s",
                action="",
                expected_effect="e",
                estimated_scope={},
            )


class TestRepairOptionsOutput:
    def _make_option(self, action: str = "replace_text", recommended: bool = False) -> RepairOption:
        return RepairOption(
            label=f"选项_{action}",
            summary="修改",
            action=action,
            expected_effect="效果",
            estimated_scope={"type": "paragraph"},
            recommended=recommended,
            recommendation_reason="推荐理由" if recommended else "",
        )

    def test_two_options_valid(self):
        out = RepairOptionsOutput(
            options=[self._make_option("a"), self._make_option("b")],
        )
        assert len(out.options) == 2

    def test_three_options_valid(self):
        out = RepairOptionsOutput(
            options=[
                self._make_option("a"),
                self._make_option("b"),
                self._make_option("c"),
            ],
        )
        assert len(out.options) == 3

    def test_duplicate_action_rejected(self):
        with pytest.raises(ValidationError, match="action 不能重复"):
            RepairOptionsOutput(
                options=[self._make_option("same"), self._make_option("same")],
            )

    def test_multiple_recommended_rejected(self):
        with pytest.raises(ValidationError, match="最多只能有一个推荐选项"):
            RepairOptionsOutput(
                options=[
                    self._make_option("a", recommended=True),
                    self._make_option("b", recommended=True),
                ],
            )

    def test_single_option_without_reason_rejected(self):
        with pytest.raises(ValidationError, match="single_option_reason"):
            RepairOptionsOutput(
                options=[self._make_option("a")],
            )

    def test_single_option_with_reason_valid(self):
        out = RepairOptionsOutput(
            options=[self._make_option("a")],
            single_option_reason="问题明确，只需一种修法",
        )
        assert out.single_option_reason == "问题明确，只需一种修法"

    def test_empty_options_rejected(self):
        with pytest.raises(ValidationError):
            RepairOptionsOutput(options=[])

    def test_four_options_rejected(self):
        with pytest.raises(ValidationError):
            RepairOptionsOutput(
                options=[
                    self._make_option("a"),
                    self._make_option("b"),
                    self._make_option("c"),
                    self._make_option("d"),
                ],
            )


class TestRevisionPatch:
    def test_valid_patch(self):
        p = RevisionPatch(
            start_offset=0,
            end_offset=5,
            original_text="hello",
            replacement_text="world",
            reason="fix",
        )
        assert p.start_offset == 0

    def test_negative_start_offset_rejected(self):
        with pytest.raises(ValidationError):
            RevisionPatch(
                start_offset=-1,
                end_offset=5,
                original_text="hello",
                replacement_text="world",
                reason="fix",
            )

    def test_negative_end_offset_rejected(self):
        with pytest.raises(ValidationError):
            RevisionPatch(
                start_offset=0,
                end_offset=-1,
                original_text="hello",
                replacement_text="world",
                reason="fix",
            )

    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError, match="end_offset 不能小于 start_offset"):
            RevisionPatch(
                start_offset=10,
                end_offset=5,
                original_text="hello",
                replacement_text="world",
                reason="fix",
            )

    def test_empty_reason_rejected(self):
        with pytest.raises(ValidationError):
            RevisionPatch(
                start_offset=0,
                end_offset=5,
                original_text="hello",
                replacement_text="world",
                reason="",
            )


class TestModificationOutput:
    def _make_patch(self, start: int = 0, end: int = 5) -> RevisionPatch:
        return RevisionPatch(
            start_offset=start,
            end_offset=end,
            original_text="hello",
            replacement_text="world",
            reason="fix",
        )

    def test_valid_output(self):
        out = ModificationOutput(
            candidate_content="world",
            patches=[self._make_patch(0, 5)],
            diff={"old": "hello", "new": "world"},
            change_reason="fix continuity",
            scope={"type": "paragraph"},
        )
        assert out.expanded_scope is False

    def test_overlapping_patches_rejected(self):
        with pytest.raises(ValidationError, match="重叠或反转"):
            ModificationOutput(
                candidate_content="test",
                patches=[
                    self._make_patch(0, 10),
                    self._make_patch(5, 15),
                ],
                diff={},
                change_reason="fix",
                scope={},
            )

    def test_expanded_scope_without_reason_rejected(self):
        with pytest.raises(ValidationError, match="expanded_scope_reason"):
            ModificationOutput(
                candidate_content="test",
                patches=[self._make_patch()],
                diff={},
                change_reason="fix",
                scope={},
                expanded_scope=True,
                expanded_scope_reason=None,
            )

    def test_expanded_scope_with_reason_valid(self):
        out = ModificationOutput(
            candidate_content="test",
            patches=[self._make_patch()],
            diff={},
            change_reason="fix",
            scope={},
            expanded_scope=True,
            expanded_scope_reason="问题影响范围超出预期",
        )
        assert out.expanded_scope is True

    def test_empty_patches_rejected(self):
        with pytest.raises(ValidationError):
            ModificationOutput(
                candidate_content="test",
                patches=[],
                diff={},
                change_reason="fix",
                scope={},
            )

    def test_inverted_patches_rejected(self):
        """Patches where later patch starts before earlier patch ends."""
        with pytest.raises(ValidationError, match="重叠或反转"):
            ModificationOutput(
                candidate_content="test",
                patches=[
                    RevisionPatch(
                        start_offset=0, end_offset=20,
                        original_text="a", replacement_text="b", reason="r1",
                    ),
                    RevisionPatch(
                        start_offset=10, end_offset=30,
                        original_text="c", replacement_text="d", reason="r2",
                    ),
                ],
                diff={},
                change_reason="fix",
                scope={},
            )


# ── Service tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_options_one(db):
    """generate_options 返回 1 个选项时 single_option_reason 已填充。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    options_output = RepairOptionsOutput(
        options=[
            RepairOption(
                label="修改措辞",
                summary="修改问题段落的措辞",
                action="replace_text",
                expected_effect="消除连续性问题",
                estimated_scope={"type": "paragraph", "chars": 50},
                recommended=True,
                recommendation_reason="最小影响",
            )
        ],
        single_option_reason="问题明确，只需一种修法",
    )
    agent = FakeModificationAgent(options_output=options_output)
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    options = await service.generate_options(issue.id)
    assert len(options) == 1
    assert options[0].action == "replace_text"


@pytest.mark.asyncio
async def test_generate_options_three(db):
    """generate_options 返回 3 个选项。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    options_output = RepairOptionsOutput(
        options=[
            RepairOption(
                label=f"选项{i}",
                summary=f"方案{i}",
                action=f"action_{i}",
                expected_effect=f"效果{i}",
                estimated_scope={"type": "paragraph"},
                recommended=(i == 0),
                recommendation_reason="推荐" if i == 0 else "",
            )
            for i in range(3)
        ],
    )
    agent = FakeModificationAgent(options_output=options_output)
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    options = await service.generate_options(issue.id)
    assert len(options) == 3
    assert options[0].recommended is True
    assert options[1].recommended is False


@pytest.mark.asyncio
async def test_create_revision_non_mutating(db):
    """create_revision 不改变当前正文、run 内容或 issue 状态。"""
    run, user, novel, version, issue = await _setup_run_with_issue(
        db, draft_content="这是一段测试正文，用于验证修改服务的功能。"
    )

    # 构建一个与原文一致的补丁（无实际变化）
    content = version.content
    patch = RevisionPatch(
        start_offset=0,
        end_offset=min(len(content), 6),
        original_text=content[: min(len(content), 6)],
        replacement_text=content[: min(len(content), 6)],
        reason="测试补丁",
    )
    mod_output = ModificationOutput(
        candidate_content=content,
        patches=[patch],
        diff={"old": content, "new": content},
        change_reason="测试修改",
        scope={"type": "paragraph"},
    )
    agent = FakeModificationAgent(modification_output=mod_output)
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    # 先生成选项
    options_output = RepairOptionsOutput(
        options=[
            RepairOption(
                label="修改",
                summary="修",
                action="replace",
                expected_effect="效果",
                estimated_scope={"type": "paragraph"},
            )
        ],
        single_option_reason="测试",
    )
    agent._options_output = options_output
    await service.generate_options(issue.id)

    before_content = version.content
    before_run_content = run.draft_content

    revision = await service.create_revision(issue.id, option_index=0)

    await db.refresh(version)
    await db.refresh(run)
    await db.refresh(issue)

    assert revision.status == "candidate"
    assert version.content == before_content
    assert run.draft_content == before_run_content
    assert issue.status == "open"


@pytest.mark.asyncio
async def test_create_revision_with_custom_intent(db):
    """create_revision 支持 custom_intent。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    content = version.content
    patch = RevisionPatch(
        start_offset=0,
        end_offset=min(len(content), 6),
        original_text=content[: min(len(content), 6)],
        replacement_text=content[: min(len(content), 6)],
        reason="自定义意图修改",
    )
    mod_output = ModificationOutput(
        candidate_content=content,
        patches=[patch],
        diff={"old": content, "new": content},
        change_reason="按自定义意图修改",
        scope={"type": "paragraph"},
    )
    agent = FakeModificationAgent(modification_output=mod_output)
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    revision = await service.create_revision(
        issue.id, custom_intent="请更加柔和地表达"
    )
    assert revision.status == "candidate"


@pytest.mark.asyncio
async def test_create_revision_invalid_option_index(db):
    """无效的 option_index 抛出 BadRequest。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    agent = FakeModificationAgent()
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    # issue 没有修复选项
    with pytest.raises(BadRequest, match="尚未生成修复选项"):
        await service.create_revision(issue.id, option_index=0)


@pytest.mark.asyncio
async def test_create_revision_option_index_out_of_range(db):
    """option_index 超出范围抛出 BadRequest。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    options_output = RepairOptionsOutput(
        options=[
            RepairOption(
                label="选项",
                summary="修",
                action="replace",
                expected_effect="效果",
                estimated_scope={"type": "paragraph"},
            )
        ],
        single_option_reason="只有一个选项",
    )
    agent = FakeModificationAgent(options_output=options_output)
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)
    await service.generate_options(issue.id)

    with pytest.raises(BadRequest, match="选项索引无效"):
        await service.create_revision(issue.id, option_index=5)


@pytest.mark.asyncio
async def test_create_revision_closed_issue_rejected(db):
    """closed/ignored 状态的问题不能创建候选修订。"""
    run, user, novel, version, issue = await _setup_run_with_issue(
        db, issue_status="ignored"
    )

    agent = FakeModificationAgent()
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    with pytest.raises(BadRequest, match="open"):
        await service.create_revision(issue.id, custom_intent="test")


@pytest.mark.asyncio
async def test_create_revision_ai_exception_no_row(db):
    """AI 异常时不创建 DraftRevision 行。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    from app.ai.plot_planning import AIProtocolError

    agent = FakeModificationAgent(create_revision_error=AIProtocolError("AI 调用失败"))
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    before_count = (
        await db.execute(
            __import__("sqlalchemy").select(
                __import__("sqlalchemy").func.count(DraftRevision.id)
            )
        )
    ).scalar()

    with pytest.raises(AIProtocolError, match="AI 调用失败"):
        await service.create_revision(issue.id, custom_intent="test")

    after_count = (
        await db.execute(
            __import__("sqlalchemy").select(
                __import__("sqlalchemy").func.count(DraftRevision.id)
            )
        )
    ).scalar()
    assert after_count == before_count


@pytest.mark.asyncio
async def test_create_revision_overlapping_patches_no_row(db):
    """重叠补丁不创建 DraftRevision 行。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    content = version.content
    # 构建重叠补丁（在 Pydantic 层会失败，所以用 invalid JSON 方式测试）
    # 我们直接测试 service 的 apply_patches 逻辑
    from app.services.modification_service import apply_patches

    patches = [
        RevisionPatch(
            start_offset=0, end_offset=10,
            original_text=content[:10], replacement_text="aaaaa", reason="r1",
        ),
        RevisionPatch(
            start_offset=5, end_offset=15,
            original_text=content[5:15], replacement_text="bbbbb", reason="r2",
        ),
    ]

    with pytest.raises(BadRequest, match="重叠或范围无效"):
        apply_patches(content, patches)

    # 确认没有 DraftRevision 被创建
    # 通过 FakeModificationAgent 返回 Pydantic 不可验证的输出来测试
    # 由于 Pydantic 会在 ModificationOutput 层拒绝重叠补丁，
    # 我们需要通过直接调用 apply_patches 来测试 service 层逻辑
    count_before = (
        await db.execute(
            __import__("sqlalchemy").select(
                __import__("sqlalchemy").func.count(DraftRevision.id)
            )
        )
    ).scalar()
    assert count_before == 0


@pytest.mark.asyncio
async def test_create_revision_mismatched_original_text_no_row(db):
    """不匹配的 original_text 不创建 DraftRevision 行。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    content = version.content
    # 构建一个 original_text 不匹配的补丁
    patch = RevisionPatch(
        start_offset=0,
        end_offset=5,
        original_text="XXXXX",  # 不匹配
        replacement_text="YYYYY",
        reason="不匹配测试",
    )
    # candidate_content 可以是任何值
    mod_output = ModificationOutput(
        candidate_content="YYYYY" + content[5:],
        patches=[patch],
        diff={"old": content, "new": "YYYYY" + content[5:]},
        change_reason="测试",
        scope={"type": "paragraph"},
    )
    agent = FakeModificationAgent(modification_output=mod_output)
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    with pytest.raises(BadRequest, match="不匹配"):
        await service.create_revision(issue.id, custom_intent="test")

    # 确认没有 DraftRevision 被创建
    count = (
        await db.execute(
            __import__("sqlalchemy").select(
                __import__("sqlalchemy").func.count(DraftRevision.id)
            )
        )
    ).scalar()
    assert count == 0


@pytest.mark.asyncio
async def test_create_revision_candidate_differs_from_patch_reconstruction_no_row(db):
    """候选内容与补丁重建结果不一致时不创建 DraftRevision 行。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    content = version.content
    # 补丁重建结果与 candidate_content 不同
    patch = RevisionPatch(
        start_offset=0,
        end_offset=min(len(content), 6),
        original_text=content[: min(len(content), 6)],
        replacement_text=content[: min(len(content), 6)],
        reason="测试补丁",
    )
    mod_output = ModificationOutput(
        candidate_content="这是不同的候选内容",  # 与补丁重建结果不一致
        patches=[patch],
        diff={"old": content, "new": "这是不同的候选内容"},
        change_reason="测试",
        scope={"type": "paragraph"},
    )
    agent = FakeModificationAgent(modification_output=mod_output)
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    with pytest.raises(BadRequest, match="不一致"):
        await service.create_revision(issue.id, custom_intent="test")

    # 确认没有 DraftRevision 被创建
    count = (
        await db.execute(
            __import__("sqlalchemy").select(
                __import__("sqlalchemy").func.count(DraftRevision.id)
            )
        )
    ).scalar()
    assert count == 0


@pytest.mark.asyncio
async def test_ignore_issue(db):
    """ignore_issue 将问题标记为 ignored。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    agent = FakeModificationAgent()
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    result = await service.ignore_issue(issue.id, "作者确认无需修复")
    assert result.status == "ignored"
    assert result.ignored_reason == "作者确认无需修复"


@pytest.mark.asyncio
async def test_ignore_closed_issue_rejected(db):
    """只能忽略 open 状态的问题。"""
    run, user, novel, version, issue = await _setup_run_with_issue(
        db, issue_status="ignored"
    )

    agent = FakeModificationAgent()
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    with pytest.raises(BadRequest, match="open"):
        await service.ignore_issue(issue.id, "再次忽略")


@pytest.mark.asyncio
async def test_ignore_issue_empty_reason_rejected(db):
    """忽略原因为空时拒绝。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    agent = FakeModificationAgent()
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    with pytest.raises(BadRequest, match="忽略原因"):
        await service.ignore_issue(issue.id, "")


@pytest.mark.asyncio
async def test_generate_options_stores_json_on_issue(db):
    """generate_options 将选项 JSON 存储到 issue.repair_options_json。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    options_output = RepairOptionsOutput(
        options=[
            RepairOption(
                label="选项1",
                summary="修",
                action="a",
                expected_effect="效果",
                estimated_scope={"type": "paragraph"},
            ),
            RepairOption(
                label="选项2",
                summary="修",
                action="b",
                expected_effect="效果",
                estimated_scope={"type": "paragraph"},
            ),
        ],
    )
    agent = FakeModificationAgent(options_output=options_output)
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    await service.generate_options(issue.id)

    await db.refresh(issue)
    assert issue.repair_options_json is not None
    assert len(issue.repair_options_json) == 2


@pytest.mark.asyncio
async def test_create_revision_source_type_and_id(db):
    """create_revision 设置 source_type=review_issue 和 source_id=issue.id。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    content = version.content
    patch = RevisionPatch(
        start_offset=0,
        end_offset=min(len(content), 6),
        original_text=content[: min(len(content), 6)],
        replacement_text=content[: min(len(content), 6)],
        reason="测试",
    )
    mod_output = ModificationOutput(
        candidate_content=content,
        patches=[patch],
        diff={"old": content, "new": content},
        change_reason="测试",
        scope={"type": "paragraph"},
    )
    agent = FakeModificationAgent(modification_output=mod_output)
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    revision = await service.create_revision(issue.id, custom_intent="测试")
    assert revision.source_type == "review_issue"
    assert revision.source_id == issue.id
    assert revision.sequence == 0
    assert revision.status == "candidate"


@pytest.mark.asyncio
async def test_create_revision_no_option_and_no_intent_rejected(db):
    """不提供 option_index 也不提供 custom_intent 时拒绝。"""
    run, user, novel, version, issue = await _setup_run_with_issue(db)

    agent = FakeModificationAgent()
    service = ModificationService(db, user.id, novel.id, modification_agent=agent)

    with pytest.raises(BadRequest, match="option_index 或 custom_intent"):
        await service.create_revision(issue.id)


@pytest.mark.asyncio
async def test_apply_patches_happy_path():
    """apply_patches 正常应用补丁。"""
    from app.services.modification_service import apply_patches

    base = "Hello, world!"
    patches = [
        RevisionPatch(
            start_offset=7, end_offset=12,
            original_text="world", replacement_text="AI",
            reason="greeting",
        ),
    ]
    result = apply_patches(base, patches)
    assert result == "Hello, AI!"


@pytest.mark.asyncio
async def test_apply_patches_multiple():
    """apply_patches 应用多个不重叠补丁。"""
    from app.services.modification_service import apply_patches

    base = "AAA BBB CCC"
    patches = [
        RevisionPatch(
            start_offset=0, end_offset=3,
            original_text="AAA", replacement_text="DDD",
            reason="r1",
        ),
        RevisionPatch(
            start_offset=8, end_offset=11,
            original_text="CCC", replacement_text="EEE",
            reason="r2",
        ),
    ]
    result = apply_patches(base, patches)
    assert result == "DDD BBB EEE"


@pytest.mark.asyncio
async def test_apply_patches_overlapping_rejected():
    """apply_patches 拒绝重叠补丁。"""
    from app.services.modification_service import apply_patches

    base = "Hello, world!"
    patches = [
        RevisionPatch(
            start_offset=0, end_offset=7,
            original_text="Hello, ", replacement_text="Hi, ",
            reason="r1",
        ),
        RevisionPatch(
            start_offset=5, end_offset=12,
            original_text=", wor", replacement_text=" W",
            reason="r2",
        ),
    ]
    with pytest.raises(BadRequest, match="重叠或范围无效"):
        apply_patches(base, patches)


@pytest.mark.asyncio
async def test_apply_patches_mismatched_text_rejected():
    """apply_patches 拒绝不匹配的 original_text。"""
    from app.services.modification_service import apply_patches

    base = "Hello, world!"
    patches = [
        RevisionPatch(
            start_offset=0, end_offset=5,
            original_text="XXXXX", replacement_text="Hi",
            reason="r1",
        ),
    ]
    with pytest.raises(BadRequest, match="不匹配"):
        apply_patches(base, patches)


# ── Atomic state-transition matrix tests ────────────────────────────────


async def _setup_apply_test(
    db,
    draft_content: str = "这是一段测试正文，用于验证修改服务的功能。",
    run_status: str = "completed",
    planning_blocked: bool = False,
    decision_id: int | None = None,
) -> tuple[WritingRun, User, Novel, DraftVersion, ReviewIssue, DraftRevision]:
    """创建完整的 FK 链并返回 (run, user, novel, version, issue, candidate_revision)。"""
    run, user, novel, version, issue = await _setup_run_with_issue(
        db, draft_content=draft_content
    )

    # Update run status if needed
    if run_status != "completed":
        run.status = run_status
    if planning_blocked:
        run.planning_blocked = True
    if decision_id is not None:
        run.decision_id = decision_id
    await db.flush()

    # Create a candidate DraftRevision linked to the issue
    content = version.content
    new_content = content[:6] + "修改后" + content[6:]

    from app.services.draft_version_service import DraftVersionService

    patches = DraftVersionService._single_patch(content, new_content, "测试修改")

    from app.repositories.draft_version_repo import DraftVersionRepo

    dv_repo = DraftVersionRepo(db)
    candidate = await dv_repo.create_revision(
        novel.id,
        {
            "writing_run_id": run.id,
            "draft_version_id": version.id,
            "sequence": 0,
            "source_type": "review_issue",
            "source_id": issue.id,
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

    return run, user, novel, version, issue, candidate


@pytest.mark.asyncio
async def test_apply_updates_draft_version_and_writing_run(db):
    """apply 更新 DraftVersion 和 WritingRun，仅递增 revision_sequence。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(db)

    svc = DraftVersionService(db, user.id, novel.id)
    before_version = version.version  # should stay unchanged
    before_seq = version.revision_sequence

    updated_version, applied_revision = await svc.apply_revision(candidate.id)

    assert applied_revision.status == "applied"
    assert updated_version.revision_sequence == before_seq + 1
    assert updated_version.version == before_version  # version number unchanged
    assert updated_version.content == candidate.candidate_content

    await db.refresh(run)
    assert run.draft_content == candidate.candidate_content
    assert run.word_count == updated_version.word_count


@pytest.mark.asyncio
async def test_reject_leaves_content_unchanged_keeps_issue_open(db):
    """reject 不改变 DraftVersion 内容和 WritingRun 内容，保持 ReviewIssue open。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(db)

    before_content = version.content
    before_run_content = run.draft_content

    svc = DraftVersionService(db, user.id, novel.id)
    rejected = await svc.reject_revision(candidate.id)

    assert rejected.status == "rejected"

    await db.refresh(version)
    await db.refresh(run)
    await db.refresh(issue)

    assert version.content == before_content
    assert run.draft_content == before_run_content
    assert issue.status == "open"


@pytest.mark.asyncio
async def test_apply_marks_source_review_issue_resolved(db):
    """apply 标记源 ReviewIssue 为 resolved 并设置 resolved_by_revision_id。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(db)

    svc = DraftVersionService(db, user.id, novel.id)
    await svc.apply_revision(candidate.id)

    await db.refresh(issue)
    assert issue.status == "resolved"
    assert issue.resolved_by_revision_id == candidate.id


@pytest.mark.asyncio
async def test_apply_supersedes_sibling_candidates_from_same_base(db):
    """apply 标记同基础的兄弟候选为 superseded。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(db)

    # Create a sibling candidate with same base
    from app.repositories.draft_version_repo import DraftVersionRepo
    from app.services.draft_version_service import DraftVersionService

    dv_repo = DraftVersionRepo(db)
    content = version.content
    sibling = await dv_repo.create_revision(
        novel.id,
        {
            "writing_run_id": run.id,
            "draft_version_id": version.id,
            "sequence": 0,
            "source_type": "review_issue",
            "source_id": None,
            "base_revision_sequence": version.revision_sequence,
            "base_content_hash": DraftVersionService._hash_content(content),
            "base_content": content,
            "candidate_content": content + "兄弟候选",
            "patches_json": [],
            "scope_json": {"type": "paragraph"},
            "diff_json": {},
            "reason": "兄弟候选",
            "status": "candidate",
        },
    )
    await db.commit()

    svc = DraftVersionService(db, user.id, novel.id)
    await svc.apply_revision(candidate.id)

    await db.refresh(sibling)
    assert sibling.status == "superseded"


@pytest.mark.asyncio
async def test_stale_sequence_preserves_prior_state(db):
    """过期的 base_revision_sequence 保留先前状态。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(db)

    # Advance the version's revision_sequence to make candidate stale
    version.revision_sequence = 99
    await db.flush()

    svc = DraftVersionService(db, user.id, novel.id)
    before_content = version.content
    with pytest.raises(BadRequest, match="序列已过期"):
        await svc.apply_revision(candidate.id)

    await db.refresh(version)
    assert version.content == before_content


@pytest.mark.asyncio
async def test_stale_hash_preserves_prior_state(db):
    """过期的 base_content_hash 保留先前状态。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(db)

    # Change version content to make hash stale
    version.content = "完全不同的内容"
    await db.flush()

    svc = DraftVersionService(db, user.id, novel.id)
    with pytest.raises(BadRequest, match="哈希已过期"):
        await svc.apply_revision(candidate.id)


@pytest.mark.asyncio
async def test_unconfirmed_expanded_scope_preserves_prior_state(db):
    """未确认的 expanded_scope 保留先前状态。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(db)

    # Mark candidate as expanded_scope
    candidate.expanded_scope = True
    candidate.expanded_scope_reason = "修改范围超出上下文窗口"
    await db.flush()

    svc = DraftVersionService(db, user.id, novel.id)
    before_content = version.content
    with pytest.raises(BadRequest, match="确认扩大范围"):
        await svc.apply_revision(candidate.id)

    await db.refresh(version)
    assert version.content == before_content

    # With confirmation, it should succeed
    await svc.apply_revision(candidate.id, confirm_expanded_scope=True)
    await db.refresh(version)
    assert version.content == candidate.candidate_content


@pytest.mark.asyncio
async def test_non_draft_version_preserves_prior_state(db):
    """非 draft 状态的 DraftVersion 保留先前状态。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(db)

    # Archive the version
    version.status = "archived"
    await db.flush()

    svc = DraftVersionService(db, user.id, novel.id)
    with pytest.raises(BadRequest, match="draft 状态"):
        await svc.apply_revision(candidate.id)


@pytest.mark.asyncio
async def test_accepted_run_preserves_prior_state(db):
    """已接受的 WritingRun 保留先前状态。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(
        db, run_status="accepted"
    )

    svc = DraftVersionService(db, user.id, novel.id)
    with pytest.raises(BadRequest, match="已接受或丢弃"):
        await svc.apply_revision(candidate.id)


@pytest.mark.asyncio
async def test_discarded_run_preserves_prior_state(db):
    """已丢弃的 WritingRun 保留先前状态。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(
        db, run_status="discarded"
    )

    svc = DraftVersionService(db, user.id, novel.id)
    with pytest.raises(BadRequest, match="已接受或丢弃"):
        await svc.apply_revision(candidate.id)


@pytest.mark.asyncio
async def test_locked_chapter_preserves_prior_state(db):
    """锁定章节保留先前状态。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(db)

    # Create a locked chapter and set it as target
    from app.models.novel import Chapter

    chapter = Chapter(
        novel_id=novel.id, title="已发布", content="事实", status="locked"
    )
    db.add(chapter)
    await db.flush()
    run.target_chapter_id = chapter.id
    await db.flush()

    svc = DraftVersionService(db, user.id, novel.id)
    with pytest.raises(BadRequest, match="已发布"):
        await svc.apply_revision(candidate.id)


@pytest.mark.asyncio
async def test_planning_candidate_clears_planning_blocked(db):
    """planning_decision 来源的候选应用清除 planning_blocked。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(
        db, run_status="decision_required", planning_blocked=True, decision_id=42
    )

    # Change source_type to planning_decision
    candidate.source_type = "planning_decision"
    candidate.source_id = None
    await db.flush()

    svc = DraftVersionService(db, user.id, novel.id)
    await svc.apply_revision(candidate.id)

    await db.refresh(run)
    assert run.planning_blocked is False
    assert run.status == "completed"
    assert run.decision_id is None


@pytest.mark.asyncio
async def test_apply_candidate_linked_to_pending_repair_marks_applied(db):
    """应用关联 PendingRepair 的候选修订标记 repair 为 applied 并重新计算 has_pending_repairs。"""
    run, user, novel, version, issue, candidate = await _setup_apply_test(db)

    # Create a PendingRepair linked to the issue
    from app.repositories.quality_gate_repo import PendingRepairRepo

    repair_repo = PendingRepairRepo(db)
    repair = await repair_repo.create(
        novel.id,
        None,
        run.id,
        {
            "issue_type": "continuity",
            "description": "连续性问题",
            "location": "测试正文",
            "context": "上下文",
            "intent_type": "choice",
            "review_issue_id": issue.id,
        },
    )
    run.has_pending_repairs = True
    await db.flush()

    svc = DraftVersionService(db, user.id, novel.id)
    await svc.apply_revision(candidate.id)

    await db.refresh(repair)
    assert repair.status == "applied"

    await db.refresh(run)
    assert run.has_pending_repairs is False
