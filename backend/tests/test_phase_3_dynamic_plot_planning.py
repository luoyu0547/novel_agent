import pytest
from pydantic import ValidationError

from app.ai.plot_planning import (
    ConflictOutput,
    DecisionOption,
    DraftGenerationOutput,
    DraftReviewOutput,
    LocalRevisionOutput,
    PlotPlanOutput,
)
from app.ai.writer import DeepSeekWritingGenerator, FakePhase3WritingGenerator
from app.ai.quality_gate import FakeQualityGateAgent
from app.core.exceptions import NotFound
from app.models.novel import Novel, Chapter
from app.models.plot_planning import (
    AuthorFoundation,
    AuthorFoundationRevision,
    DraftRevision,
    PlotUnit,
    PlotPlanRevision,
    PlanningDecision,
)
from app.models.user import User
from app.models.writing import ChapterPlan, ChapterBrief, WritingRun
from app.schemas.plot_planning import ChooseDecisionRequest
from app.services.plot_planning_service import PlotPlanningService
from app.services.writing_service import WritingService


@pytest.fixture
async def novel_and_headers(client):
    response = await client.post("/api/v1/auth/register", json={"username": "p6_user", "password": "password123"})
    token = response.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post("/api/v1/novels", headers=headers, json={"title": "P6测试", "description": "决策与发布测试", "genre": "古风"})
    novel = response.json()["data"]
    return novel, headers


async def create_locked_chapter(client, novel_id, headers, content="发布事实"):
    response = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        headers=headers,
        json={"title": "已发布章", "content": content, "status": "draft"},
    )
    chapter = response.json()["data"]
    from app.core.database import async_session_factory
    from app.repositories.novel_repo import ChapterRepo
    async with async_session_factory() as db:
        repo = ChapterRepo(db)
        ch = await repo.get_by_id(chapter["id"])
        await repo.update(ch, title=None, content=None, summary=None, status="locked")
    response = await client.get(f"/api/v1/novels/{novel_id}/chapters/{chapter['id']}", headers=headers)
    return response.json()["data"]


@pytest.mark.asyncio
async def test_phase3_models_preserve_revision_and_decision_boundaries(db):
    foundation = AuthorFoundation(
        novel_id=1,
        outline="作者已有第一卷大纲",
        current_intent="先完成边城调查",
        stage_goal="主角发现密令来源",
        constraints_json={"tone": "克制", "must_keep": ["旧案线索"]},
        version=1,
    )
    db.add(foundation)
    await db.flush()
    revision = AuthorFoundationRevision(
        novel_id=1,
        foundation_id=foundation.id,
        version=1,
        snapshot_json={"outline": foundation.outline, "stage_goal": foundation.stage_goal},
        change_reason="initial",
    )
    db.add(revision)
    await db.flush()
    unit = PlotUnit(
        novel_id=1,
        title="第一卷：边城旧案",
        scope_type="volume",
        start_position=1,
        end_position=5,
        author_goal="查清密令来源",
        start_state="主角抵达边城",
        end_state="主角确认旧案与密令相连",
        foundation_revision_id=revision.id,
        status="draft",
    )
    db.add(unit)
    await db.flush()
    plan = PlotPlanRevision(
        novel_id=1,
        plot_unit_id=unit.id,
        foundation_revision_id=revision.id,
        version=1,
        plan_json={"core_conflict": "调查会触动守城势力"},
        change_reason="initial generation",
        status="draft",
    )
    db.add(plan)
    await db.flush()
    decision = PlanningDecision(
        novel_id=1,
        plot_unit_id=unit.id,
        plot_plan_revision_id=plan.id,
        source="during_review",
        status="pending",
        conflict_summary="新目标要求推翻已发布事实",
        evidence_json={"published_chapter_ids": [10]},
        options_json=[
            {"label": "补充因果", "consequence": "保留事实"},
            {"label": "改写未来", "consequence": "延后揭示"},
        ],
        recommended_index=0,
        recommendation_reason="不会修改已发布章节",
        impact_scope_json={"type": "scene", "start": 2, "end": 2},
    )
    db.add(decision)
    await db.flush()
    assert plan.status == "draft"
    assert decision.source == "during_review"
    assert len(decision.options_json) == 2


def test_decision_request_requires_option_or_custom_intent():
    with pytest.raises(ValidationError):
        ChooseDecisionRequest()
    assert ChooseDecisionRequest(option_index=1).option_index == 1
    assert ChooseDecisionRequest(custom_intent="保留事实并延后揭示").custom_intent


def test_conflict_output_requires_two_real_options():
    result = ConflictOutput(
        source="during_generation",
        core_conflict="已发布事实与新目标冲突",
        options=[
            DecisionOption(label="补充因果", action="supplement", consequence="保留已发布事实"),
            DecisionOption(label="改变未来目标", action="change_goal", consequence="不触碰正文"),
        ],
        recommended_index=0,
        recommendation_reason="影响范围最小",
        impact_scope={"type": "scene", "start": 2, "end": 2},
    )
    assert len(result.options) == 2


def test_conflict_output_rejects_duplicate_or_fake_options():
    with pytest.raises(ValidationError):
        ConflictOutput(
            source="during_review",
            core_conflict="冲突",
            options=[
                DecisionOption(label="同一方案", action="same", consequence="保留"),
                DecisionOption(label="同一方案", action="same", consequence="保留"),
            ],
            recommended_index=0,
            recommendation_reason="理由",
            impact_scope={"type": "paragraph"},
        )


@pytest.mark.asyncio
async def test_fake_generation_can_return_decision_required():
    generator = FakePhase3WritingGenerator(
        draft_result=DraftGenerationOutput(
            status="decision_required",
            draft="不越过冲突点的部分正文",
            conflict=ConflictOutput(
                source="during_generation",
                core_conflict="世界规则不允许新目标",
                options=[
                    DecisionOption(label="补充代价", action="add_cost", consequence="保留规则"),
                    DecisionOption(label="调整目标", action="adjust_goal", consequence="保留角色动机"),
                ],
                recommended_index=0,
                recommendation_reason="最小影响",
                impact_scope={"type": "scene", "start": 1, "end": 1},
            ),
        )
    )
    result = await generator.generate_draft_result({"plot_plan": {}})
    assert result.status == "decision_required"
    assert result.conflict is not None


# ---- Task 1: Production generator default and Pydantic normalization ----


def test_plot_plan_output_normalizes_to_dict():
    output = PlotPlanOutput(
        starting_state="主角抵达边城",
        stage_goal="查清旧案",
        core_conflict="调查触动守城势力",
        key_turns=[{"order": 1, "event": "发现线索", "required": True}],
        progression=[{"order": 1, "chapter_position": 1, "purpose": "推进调查", "scenes": ["牢狱"]}],
        completion_criteria=["找到关键证人"],
    )
    assert PlotPlanningService._normalize_plot_plan_output(output)["core_conflict"] == "调查触动守城势力"


@pytest.mark.asyncio
async def test_plot_planning_service_defaults_to_deepseek(db):
    service = PlotPlanningService(db=db, user_id=1, novel_id=1)
    assert isinstance(service.generator, DeepSeekWritingGenerator)


# ---- Service-level tests (Task 3: Plot Planning Service & Context Package) ----


@pytest.mark.asyncio
async def test_foundation_update_creates_history_without_decision(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    await db.commit()

    from app.services.plot_planning_service import PlotPlanningService

    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=FakePhase3WritingGenerator())
    first = await service.update_foundation(
        {"outline": "第一版大纲", "current_intent": "调查", "stage_goal": "找到证据", "constraints_json": {}},
        change_reason="initial",
    )
    assert first.version == 1
    second = await service.update_foundation(
        {"stage_goal": "找到证据并保护证人"},
        change_reason="作者调整阶段目标",
    )
    assert second.version == 2
    revisions = await service.list_foundation_revisions()
    assert [r.version for r in revisions] == [2, 1]
    assert await service.list_pending_decisions() == []


@pytest.mark.asyncio
async def test_foundation_update_marks_active_plans_stale(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    await db.commit()

    from app.services.plot_planning_service import PlotPlanningService

    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=FakePhase3WritingGenerator())
    await service.update_foundation(
        {"outline": "大纲", "current_intent": "意图", "stage_goal": "目标", "constraints_json": {}},
        change_reason="initial",
    )
    unit = await service.create_plot_unit({
        "title": "第一卷", "scope_type": "volume", "start_position": 1, "end_position": 10,
    })
    plan = await service.generate_plan(unit.id)
    await service.confirm_plan(unit.id, plan.id)
    await service.update_foundation({"stage_goal": "新目标"}, change_reason="调整")
    revisions = await service.list_plan_revisions(unit.id)
    stale = next(r for r in revisions if r.id == plan.id)
    assert stale.status == "stale"


@pytest.mark.asyncio
async def test_plot_unit_creation_and_ownership(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    await db.commit()

    from app.services.plot_planning_service import PlotPlanningService

    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=FakePhase3WritingGenerator())
    await service.update_foundation(
        {"outline": "大纲", "current_intent": "意图", "stage_goal": "目标", "constraints_json": {}},
        change_reason="initial",
    )
    unit = await service.create_plot_unit({
        "title": "第一卷", "scope_type": "volume", "start_position": 1, "end_position": 10,
    })
    assert unit.title == "第一卷"
    assert unit.novel_id == 1
    units = await service.list_plot_units()
    assert len(units) == 1
    fetched = await service.get_plot_unit(unit.id)
    assert fetched.id == unit.id


@pytest.mark.asyncio
async def test_generate_plan_creates_draft_revision(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    await db.commit()

    from app.services.plot_planning_service import PlotPlanningService

    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=FakePhase3WritingGenerator())
    await service.update_foundation(
        {"outline": "大纲", "current_intent": "意图", "stage_goal": "目标", "constraints_json": {}},
        change_reason="initial",
    )
    unit = await service.create_plot_unit({
        "title": "第一卷", "scope_type": "volume", "start_position": 1, "end_position": 10,
    })
    plan = await service.generate_plan(plot_unit_id=unit.id, author_input="调查主线")
    assert plan.status == "draft"
    assert plan.plot_unit_id == unit.id


@pytest.mark.asyncio
async def test_confirm_plan_archives_previous_and_activates_selected(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    await db.commit()

    from app.services.plot_planning_service import PlotPlanningService

    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=FakePhase3WritingGenerator())
    await service.update_foundation(
        {"outline": "大纲", "current_intent": "意图", "stage_goal": "目标", "constraints_json": {}},
        change_reason="initial",
    )
    unit = await service.create_plot_unit({
        "title": "第一卷", "scope_type": "volume", "start_position": 1, "end_position": 10,
    })
    plan1 = await service.generate_plan(unit.id)
    confirmed1 = await service.confirm_plan(unit.id, plan1.id)
    assert confirmed1.status == "active"
    plan2 = await service.generate_plan(unit.id)
    confirmed2 = await service.confirm_plan(unit.id, plan2.id)
    assert confirmed2.status == "active"
    revisions = await service.list_plan_revisions(unit.id)
    superseded_count = sum(1 for r in revisions if r.status == "superseded")
    active_count = sum(1 for r in revisions if r.status == "active")
    assert superseded_count == 1
    assert active_count == 1


@pytest.mark.asyncio
async def test_generate_plan_rolls_back_on_generator_error(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    await db.commit()

    from app.services.plot_planning_service import PlotPlanningService

    class BadGenerator(FakePhase3WritingGenerator):
        async def generate_plot_plan(self, foundation, plot_unit, published_canon):
            raise ValueError("模拟失败")

    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=BadGenerator())
    await service.update_foundation(
        {"outline": "大纲", "current_intent": "意图", "stage_goal": "目标", "constraints_json": {}},
        change_reason="initial",
    )
    unit = await service.create_plot_unit({
        "title": "第一卷", "scope_type": "volume", "start_position": 1, "end_position": 10,
    })
    unit_id = unit.id
    with pytest.raises(ValueError, match="模拟失败"):
        await service.generate_plan(unit_id)
    plans = await service.list_plan_revisions(unit_id)
    assert len(plans) == 0


@pytest.mark.asyncio
async def test_planning_service_raises_not_found_for_wrong_novel(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    await db.commit()

    from app.services.plot_planning_service import PlotPlanningService

    service = PlotPlanningService(db=db, user_id=1, novel_id=999, generator=FakePhase3WritingGenerator())
    with pytest.raises(NotFound):
        await service.create_plot_unit({
            "title": "测试", "scope_type": "volume", "start_position": 1, "end_position": 1,
        })


@pytest.mark.asyncio
async def test_context_contains_only_locked_chapters_and_plan_snapshot(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说", description="描述", genre="推理", style_guide="克制冷调")
    db.add(novel)
    locked = Chapter(id=1, novel_id=1, title="已发布章", content="不可修改事实", status="locked")
    draft_ch = Chapter(id=2, novel_id=1, title="未发布章", content="候选正文", status="draft")
    db.add_all([locked, draft_ch])
    chapter_plan = ChapterPlan(id=1, novel_id=1, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(chapter_plan)
    brief = ChapterBrief(id=1, novel_id=1, chapter_plan_id=1, brief_json={"writing_goal": "测试"}, length_contract_json={}, status="ready")
    db.add(brief)
    foundation = AuthorFoundation(id=1, novel_id=1, outline="大纲", current_intent="意图", stage_goal="阶段目标", constraints_json={}, version=1)
    db.add(foundation)
    await db.flush()
    revision = AuthorFoundationRevision(id=1, novel_id=1, foundation_id=1, version=1, snapshot_json={"outline": "大纲"}, change_reason="initial")
    db.add(revision)
    await db.flush()
    unit = PlotUnit(id=1, novel_id=1, title="单元", scope_type="volume", start_position=1, end_position=5, foundation_revision_id=1)
    db.add(unit)
    await db.flush()
    plot_plan = PlotPlanRevision(
        id=1, novel_id=1, plot_unit_id=1, foundation_revision_id=1, version=1,
        plan_json={"core_conflict": "冲突"}, status="active",
    )
    db.add(plot_plan)
    await db.commit()

    from app.services.context_package_service import ContextPackageService

    context = await ContextPackageService(db, user_id=1, novel_id=1).build_for_brief(
        brief_id=1,
        plot_plan_revision_id=1,
        author_input="本次让调查转向码头",
    )
    chapter_ids = [item["id"] for item in context["published_canon"]["chapters"]]
    assert chapter_ids == [1]
    assert "候选正文" not in str(context["published_canon"])
    assert context["snapshot"]["plot_plan_revision_id"] == 1
    assert context["author_input"] == "本次让调查转向码头"


class RecordingPhase3WritingGenerator(FakePhase3WritingGenerator):
    def __init__(self):
        super().__init__()
        self.last_context = None

    async def generate_draft_result(self, context_package):
        self.last_context = context_package
        return await super().generate_draft_result(context_package)


def decision_required_result():
    return DraftGenerationOutput(
        status="decision_required",
        draft="不越过冲突点的部分正文",
        conflict=ConflictOutput(
            source="during_generation",
            core_conflict="冲突",
            options=[
                DecisionOption(label="补充因果", action="supplement", consequence="保留事实"),
                DecisionOption(label="改写未来", action="rewrite_future", consequence="延后揭示"),
            ],
            recommended_index=0,
            recommendation_reason="最小影响",
            impact_scope={"type": "scene"},
        ),
    )


@pytest.mark.asyncio
async def test_phase3_writing_run_passes_plan_and_locked_canon_to_generator(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说", description="描述", genre="推理", style_guide="克制冷调")
    db.add(novel)
    locked = Chapter(id=1, novel_id=1, title="已发布章", content="不可修改内容", status="locked")
    draft_ch = Chapter(id=2, novel_id=1, title="未发布章", content="可修改内容", status="draft")
    db.add_all([locked, draft_ch])
    chapter_plan = ChapterPlan(id=1, novel_id=1, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(chapter_plan)
    brief = ChapterBrief(id=1, novel_id=1, chapter_plan_id=1, brief_json={"writing_goal": "测试"}, length_contract_json={"target_words": 10, "min_words": 1, "max_words": 100}, status="ready")
    db.add(brief)
    foundation = AuthorFoundation(id=1, novel_id=1, outline="大纲", current_intent="意图", stage_goal="阶段目标", constraints_json={}, version=1)
    db.add(foundation)
    await db.flush()
    revision = AuthorFoundationRevision(id=1, novel_id=1, foundation_id=1, version=1, snapshot_json={"outline": "大纲"}, change_reason="initial")
    db.add(revision)
    await db.flush()
    unit = PlotUnit(id=1, novel_id=1, title="单元", scope_type="volume", start_position=1, end_position=5, foundation_revision_id=1)
    db.add(unit)
    await db.flush()
    plot_plan = PlotPlanRevision(
        id=1, novel_id=1, plot_unit_id=1, foundation_revision_id=1, version=1,
        plan_json={"core_conflict": "冲突"}, status="active",
    )
    db.add(plot_plan)
    await db.commit()

    generator = RecordingPhase3WritingGenerator()
    service = WritingService(db=db, user_id=1, novel_id=1, generator=generator, gate_agent=FakeQualityGateAgent())
    run = await service.create_writing_run(
        brief_id=1,
        plot_plan_revision_id=1,
        author_input="本次必须让证人活着离开",
    )
    assert run.status == "completed"
    assert generator.last_context["snapshot"]["plot_plan_revision_id"] == 1
    assert generator.last_context["author_input"] == "本次必须让证人活着离开"
    chapter_statuses = [item["status"] for item in generator.last_context["published_canon"]["chapters"]]
    assert chapter_statuses == ["locked"]
    assert run.context_snapshot_json["foundation_revision_id"] is not None


@pytest.mark.asyncio
async def test_decision_required_preserves_partial_unpublished_draft(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说", description="描述", genre="推理", style_guide="克制冷调")
    db.add(novel)
    locked = Chapter(id=1, novel_id=1, title="已锁定章", content="不可修改内容", status="locked")
    draft_ch = Chapter(id=2, novel_id=1, title="未发布章", content="可修改内容", status="draft")
    db.add_all([locked, draft_ch])
    chapter_plan = ChapterPlan(id=1, novel_id=1, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(chapter_plan)
    brief = ChapterBrief(id=1, novel_id=1, chapter_plan_id=1, brief_json={"writing_goal": "测试"}, length_contract_json={"target_words": 10, "min_words": 1, "max_words": 100}, status="ready")
    db.add(brief)
    foundation = AuthorFoundation(id=1, novel_id=1, outline="大纲", current_intent="意图", stage_goal="阶段目标", constraints_json={}, version=1)
    db.add(foundation)
    await db.flush()
    revision = AuthorFoundationRevision(id=1, novel_id=1, foundation_id=1, version=1, snapshot_json={"outline": "大纲"}, change_reason="initial")
    db.add(revision)
    await db.flush()
    unit = PlotUnit(id=1, novel_id=1, title="单元", scope_type="volume", start_position=1, end_position=5, foundation_revision_id=1)
    db.add(unit)
    await db.flush()
    plot_plan = PlotPlanRevision(
        id=1, novel_id=1, plot_unit_id=1, foundation_revision_id=1, version=1,
        plan_json={"core_conflict": "冲突"}, status="active",
    )
    db.add(plot_plan)
    await db.commit()

    generator = FakePhase3WritingGenerator(draft_result=decision_required_result())
    service = WritingService(db=db, user_id=1, novel_id=1, generator=generator, gate_agent=FakeQualityGateAgent())
    run = await service.create_writing_run(brief_id=1, plot_plan_revision_id=1)
    assert run.status == "decision_required"
    assert run.planning_blocked is True
    assert run.decision_id is not None
    assert run.draft_content == "不越过冲突点的部分正文"
    ch_locked = await db.get(Chapter, 1)
    assert ch_locked is not None and ch_locked.status == "locked"
    ch_draft = await db.get(Chapter, 2)
    assert ch_draft is not None and ch_draft.status == "draft"


# ---- Task 5: Shared decision, draft review, quality routing ----


def conflict_output():
    return ConflictOutput(
        source="during_generation",
        core_conflict="已发布事实与新目标冲突",
        options=[
            DecisionOption(label="补充因果", action="补充", consequence="保留已发布事实"),
            DecisionOption(label="改变未来目标", action="改变", consequence="不触碰正文"),
        ],
        recommended_index=0,
        recommendation_reason="影响范围最小",
        impact_scope={"type": "scene", "start": 2, "end": 2},
    )


@pytest.mark.asyncio
async def test_generation_and_review_use_same_decision_shape(db):
    from app.services.plot_planning_service import PlotPlanningService

    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    chapter_plan = ChapterPlan(id=1, novel_id=1, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(chapter_plan)
    brief = ChapterBrief(id=1, novel_id=1, chapter_plan_id=1, brief_json={"writing_goal": "测试"}, length_contract_json={}, status="ready")
    db.add(brief)
    run = WritingRun(
        id=1, novel_id=1, chapter_brief_id=1, context_package_id=1,
        status="completed", draft_content="测试正文",
        context_snapshot_json={},
    )
    db.add(run)
    await db.commit()

    gen_service = PlotPlanningService(db=db, user_id=1, novel_id=1)
    rev_service = PlotPlanningService(db=db, user_id=1, novel_id=1)
    conflict = conflict_output()
    during_generation = await gen_service.create_decision_from_conflict(
        conflict, source="during_generation", run_id=1,
    )
    during_review = await rev_service.create_decision_from_conflict(
        conflict.model_copy(update={"source": "during_review"}),
        source="during_review", run_id=1,
    )
    assert during_generation.conflict_summary == during_review.conflict_summary
    assert during_generation.options_json == during_review.options_json
    assert during_generation.source == "during_generation"
    assert during_review.source == "during_review"


@pytest.mark.asyncio
async def test_review_does_not_turn_style_issue_into_decision(db):
    from app.services.plot_planning_service import PlotPlanningService

    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    chapter_plan = ChapterPlan(id=1, novel_id=1, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(chapter_plan)
    brief = ChapterBrief(id=1, novel_id=1, chapter_plan_id=1, brief_json={"writing_goal": "测试"}, length_contract_json={}, status="ready")
    db.add(brief)
    run = WritingRun(
        id=1, novel_id=1, chapter_brief_id=1, context_package_id=1,
        status="completed", draft_content="测试正文",
        context_snapshot_json={"foundation_revision_id": 1},
    )
    db.add(run)
    await db.commit()

    generator = FakePhase3WritingGenerator(
        review=DraftReviewOutput(
            narrative_conflicts=[],
            quality_issues=[{"issue_type": "style", "severity": "warning", "description": "句式重复", "location": "第2段"}],
        )
    )
    service = WritingService(db=db, user_id=1, novel_id=1, generator=generator)
    result = await service.review_writing_run(1)
    assert result["decision"] is None
    assert len(result["review_issues"]) == 1
    assert await PlotPlanningService(db, 1, 1).list_pending_decisions() == []


# ---- Task 6: Decision choose/apply, locked chapter, publish boundary ----


@pytest.mark.asyncio
async def test_choose_decision_preserves_unaffected_text_and_creates_new_plan(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    await db.flush()

    from app.services.plot_planning_service import PlotPlanningService
    from app.repositories.plot_planning_repo import PlotPlanningRepo

    foundation = await PlotPlanningService(db, 1, 1).update_foundation(
        {"outline": "大纲", "current_intent": "意图", "stage_goal": "目标", "constraints_json": {}},
        change_reason="initial",
    )

    repo = PlotPlanningRepo(db)
    revision = await repo.get_latest_foundation_revision(1)
    unit = await PlotPlanningService(db, 1, 1).create_plot_unit({
        "title": "第一卷", "scope_type": "volume", "start_position": 1, "end_position": 10,
    })
    plan = await PlotPlanningService(db, 1, 1).generate_plan(unit.id)
    confirmed = await PlotPlanningService(db, 1, 1).confirm_plan(unit.id, plan.id)
    assert confirmed.status == "active"

    # Create a writing run with target_chapter_id so it can be referenced
    from app.models.writing import ChapterBrief, ChapterPlan, WritingRun
    cp = ChapterPlan(id=10, novel_id=1, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(cp)
    await db.flush()
    brief = ChapterBrief(id=10, novel_id=1, chapter_plan_id=10, brief_json={"writing_goal": "测试"}, length_contract_json={}, status="ready")
    db.add(brief)
    await db.flush()
    run = WritingRun(
        id=10, novel_id=1, chapter_brief_id=10, context_package_id=1,
        status="completed", draft_content="开头不变。旧冲突场景。结尾不变。",
        planning_blocked=True,
        context_snapshot_json={"plot_plan_revision_id": confirmed.id},
    )
    db.add(run)
    await db.flush()

    # Create a pending decision linked to this run
    decision = await repo.create_decision(1, {
        "plot_unit_id": unit.id,
        "plot_plan_revision_id": confirmed.id,
        "writing_run_id": 10,
        "source": "during_generation",
        "status": "pending",
        "conflict_summary": "冲突需要解决",
        "evidence_json": {},
        "options_json": [
            {"label": "补充因果", "action": "补充", "consequence": "保留事实"},
            {"label": "改写未来", "action": "改写", "consequence": "延后揭示"},
        ],
        "recommended_index": 0,
        "recommendation_reason": "最小影响",
        "impact_scope_json": {"type": "paragraph", "start": 2, "end": 2},
    })
    await db.commit()

    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=FakePhase3WritingGenerator(
        revision=LocalRevisionOutput(
            candidate_content="开头不变。修订后的冲突场景。结尾不变。",
            scope={"type": "paragraph", "start": 2, "end": 2},
            diff={"removed": ["旧冲突场景"], "added": ["修订后的冲突场景"]},
            plan_patch={"progression": [{"order": 2, "purpose": "承接补充因果"}]},
            expanded_scope=False,
            expansion_reason="",
        )
    ))
    decision, new_plan, revision, run = await service.choose_decision(decision.id, option_index=0)
    assert decision.status == "resolved"
    assert new_plan.version == 2
    assert new_plan.status == "active"
    assert revision.status == "candidate"
    assert revision.candidate_content.startswith("开头不变。")
    assert revision.candidate_content.endswith("结尾不变。")
    assert run.planning_blocked is False


@pytest.mark.asyncio
async def test_choose_decision_rolls_back_on_generator_failure(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    await db.flush()

    from app.services.plot_planning_service import PlotPlanningService
    from app.repositories.plot_planning_repo import PlotPlanningRepo

    await PlotPlanningService(db, 1, 1).update_foundation(
        {"outline": "大纲", "current_intent": "意图", "stage_goal": "目标", "constraints_json": {}},
        change_reason="initial",
    )
    repo = PlotPlanningRepo(db)
    unit = await PlotPlanningService(db, 1, 1).create_plot_unit({
        "title": "第一卷", "scope_type": "volume", "start_position": 1, "end_position": 10,
    })
    plan = await PlotPlanningService(db, 1, 1).generate_plan(unit.id)
    confirmed = await PlotPlanningService(db, 1, 1).confirm_plan(unit.id, plan.id)

    from app.models.writing import ChapterPlan, ChapterBrief, WritingRun
    cp = ChapterPlan(id=20, novel_id=1, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(cp)
    await db.flush()
    brief = ChapterBrief(id=20, novel_id=1, chapter_plan_id=20, brief_json={"writing_goal": "测试"}, length_contract_json={}, status="ready")
    db.add(brief)
    await db.flush()
    run = WritingRun(
        id=20, novel_id=1, chapter_brief_id=20, context_package_id=1,
        status="completed", draft_content="草稿内容",
        planning_blocked=True,
        context_snapshot_json={"plot_plan_revision_id": confirmed.id},
    )
    db.add(run)
    await db.flush()

    decision = await repo.create_decision(1, {
        "plot_unit_id": unit.id, "plot_plan_revision_id": confirmed.id, "writing_run_id": 20,
        "source": "during_generation", "status": "pending",
        "conflict_summary": "冲突", "evidence_json": {},
        "options_json": [{"label": "A", "action": "a", "consequence": "c"}, {"label": "B", "action": "b", "consequence": "d"}],
        "recommended_index": 0, "recommendation_reason": "最小", "impact_scope_json": {},
    })
    await db.commit()

    class BadGenerator(FakePhase3WritingGenerator):
        async def revise_draft(self, context_package, draft, conflict, selected_direction):
            raise ValueError("AI revision failed")

    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=BadGenerator())
    with pytest.raises(ValueError, match="AI revision failed"):
        await service.choose_decision(decision.id, option_index=0)

    # Decision should still be pending, old plan still active
    still_pending = await repo.get_decision(decision.id, 1)
    assert still_pending.status == "pending"
    old_plan = await repo.get_plan_revision(confirmed.id, 1)
    assert old_plan.status == "active"


@pytest.mark.asyncio
async def test_locked_chapter_rejects_update_accept_and_delete(client, novel_and_headers):
    novel, headers = novel_and_headers
    chapter = await create_locked_chapter(client, novel["id"], headers, "发布事实")
    update = await client.put(
        f"/api/v1/novels/{novel['id']}/chapters/{chapter['id']}",
        headers=headers,
        json={"content": "试图改写"},
    )
    assert update.status_code == 400
    delete = await client.delete(
        f"/api/v1/novels/{novel['id']}/chapters/{chapter['id']}",
        headers=headers,
    )
    assert delete.status_code == 400


@pytest.mark.asyncio
async def test_accept_writing_run_rejects_decision_required(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    from app.models.writing import ChapterPlan, ChapterBrief, WritingRun
    cp = ChapterPlan(id=30, novel_id=1, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(cp)
    brief = ChapterBrief(id=30, novel_id=1, chapter_plan_id=30, brief_json={"writing_goal": "测试"}, length_contract_json={}, status="ready")
    db.add(brief)
    run = WritingRun(
        id=30, novel_id=1, chapter_brief_id=30, context_package_id=1,
        status="decision_required", draft_content="草稿",
    )
    db.add(run)
    await db.commit()

    svc = WritingService(db=db, user_id=1, novel_id=1)
    from app.core.exceptions import AppException
    with pytest.raises(AppException, match="决策"):
        await svc.accept_writing_run(30)


@pytest.mark.asyncio
async def test_accept_writing_run_rejects_planning_blocked(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    from app.models.writing import ChapterPlan, ChapterBrief, WritingRun
    cp = ChapterPlan(id=31, novel_id=1, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(cp)
    brief = ChapterBrief(id=31, novel_id=1, chapter_plan_id=31, brief_json={"writing_goal": "测试"}, length_contract_json={}, status="ready")
    db.add(brief)
    run = WritingRun(
        id=31, novel_id=1, chapter_brief_id=31, context_package_id=1,
        status="completed", draft_content="草稿",
        planning_blocked=True,
    )
    db.add(run)
    await db.commit()

    svc = WritingService(db=db, user_id=1, novel_id=1)
    from app.core.exceptions import AppException
    with pytest.raises(AppException, match="规划阻塞"):
        await svc.accept_writing_run(31)


@pytest.mark.asyncio
async def test_accept_writing_run_rejects_write_to_locked_chapter(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    chapter = Chapter(id=1, novel_id=1, title="已发布", content="事实", status="locked")
    db.add(chapter)
    await db.flush()

    from app.models.writing import ChapterPlan, ChapterBrief, WritingRun
    cp = ChapterPlan(id=33, novel_id=1, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(cp)
    brief = ChapterBrief(id=33, novel_id=1, chapter_plan_id=33, brief_json={"writing_goal": "测试"}, length_contract_json={}, status="ready")
    db.add(brief)
    run = WritingRun(
        id=33, novel_id=1, chapter_brief_id=33,
        context_package_id=1,
        status="completed", draft_content="新草稿",
        target_chapter_id=1,
    )
    db.add(run)
    await db.commit()

    svc = WritingService(db=db, user_id=1, novel_id=1)
    from app.core.exceptions import AppException
    with pytest.raises(AppException, match="已发布章节不可覆盖"):
        await svc.accept_writing_run(33)


@pytest.mark.asyncio
async def test_publish_chapter_rejects_locked(client, novel_and_headers):
    novel, headers = novel_and_headers
    chapter = await create_locked_chapter(client, novel["id"], headers, "已发布")
    resp = await client.put(
        f"/api/v1/novels/{novel['id']}/chapters/{chapter['id']}/publish",
        headers=headers,
        json={},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_publish_chapter_rejects_pending_decisions(client, novel_and_headers):
    novel, headers = novel_and_headers
    # Create a draft chapter
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapters",
        headers=headers,
        json={"title": "待发布", "content": "草稿", "status": "draft"},
    )
    chapter = resp.json()["data"]

    # Create a pending decision directly
    from app.core.database import async_session_factory
    from app.repositories.plot_planning_repo import PlotPlanningRepo
    async with async_session_factory() as db:
        repo = PlotPlanningRepo(db)
        await repo.create_decision(novel["id"], {
            "writing_run_id": 0,
            "source": "during_generation",
            "status": "pending",
            "conflict_summary": "阻碍发布的冲突",
            "evidence_json": {},
            "options_json": [{"label": "A", "action": "a", "consequence": "c"}],
            "recommended_index": 0,
            "recommendation_reason": "唯一方案",
            "impact_scope_json": {},
        })
        await db.commit()

    resp = await client.put(
        f"/api/v1/novels/{novel['id']}/chapters/{chapter['id']}/publish",
        headers=headers,
        json={},
    )
    assert resp.status_code == 400
    assert "待处理决策" in resp.json()["message"] or "决策" in resp.json()["message"]


@pytest.mark.asyncio
async def test_publish_chapter_success(client, novel_and_headers):
    novel, headers = novel_and_headers
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapters",
        headers=headers,
        json={"title": "可发布", "content": "正文内容", "status": "draft"},
    )
    chapter = resp.json()["data"]

    resp = await client.put(
        f"/api/v1/novels/{novel['id']}/chapters/{chapter['id']}/publish",
        headers=headers,
        json={},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "locked"


@pytest.mark.asyncio
async def test_update_foundation_supersedes_pending_decisions(db):
    user = User(id=1, username="tester", hashed_password="x")
    db.add(user)
    novel = Novel(id=1, user_id=1, title="测试小说")
    db.add(novel)
    await db.commit()

    from app.services.plot_planning_service import PlotPlanningService
    from app.repositories.plot_planning_repo import PlotPlanningRepo

    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=FakePhase3WritingGenerator())
    await service.update_foundation(
        {"outline": "大纲", "current_intent": "意图", "stage_goal": "目标", "constraints_json": {}},
        change_reason="initial",
    )
    repo = PlotPlanningRepo(db)
    decision = await repo.create_decision(1, {
        "writing_run_id": 0,
        "source": "during_generation",
        "status": "pending",
        "conflict_summary": "旧冲突",
        "evidence_json": {},
        "options_json": [{"label": "A", "action": "a", "consequence": "c"}],
        "recommended_index": 0,
        "recommendation_reason": "唯一",
        "impact_scope_json": {},
    })
    await db.commit()

    await service.update_foundation({"stage_goal": "新目标"}, change_reason="调整")
    decisions = await service.list_decisions()
    superseded = [d for d in decisions if d.status == "superseded"]
    assert len(superseded) == 1
    assert superseded[0].id == decision.id


# ===== Task 8: E2E scenario test =====


@pytest.mark.asyncio
async def test_phase3_e2e_full_scenario(client, novel_and_headers, db):
    from app.services.writing_service import WritingService
    from app.services.plot_planning_service import PlotPlanningService
    from app.models.writing import ChapterPlan, ChapterBrief, WritingRun
    from app.ai.plot_planning import LocalRevisionOutput

    novel, headers = novel_and_headers
    novel_id = novel["id"]

    # 1. Set author foundation via API
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/author-foundation",
        headers=headers,
        json={
            "outline": "作者已有第一卷大纲：主角在边城调查旧案",
            "current_intent": "完成边城调查",
            "stage_goal": "查清旧案并保护证人",
            "constraints_json": {"tone": "克制"},
        },
    )
    assert resp.status_code == 200

    # 2. Create a locked chapter
    await create_locked_chapter(client, novel_id, headers, "已发布的锁定事实")

    # 3. Create plot unit via API
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/plot-units",
        headers=headers,
        json={
            "title": "第一卷", "scope_type": "volume",
            "start_position": 1, "end_position": 5,
            "author_goal": "查清旧案",
        },
    )
    assert resp.status_code == 200
    unit = resp.json()["data"]

    # 4. Generate plan via API
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/plot-units/{unit['id']}/plans/generate",
        headers=headers,
        json={"author_input": ""},
    )
    assert resp.status_code == 200
    draft_plan = resp.json()["data"]
    assert draft_plan["status"] == "draft"

    # 5. Confirm plan via API
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/plot-units/{unit['id']}/plans/{draft_plan['id']}/confirm",
        headers=headers,
    )
    assert resp.status_code == 200
    active_plan = resp.json()["data"]
    assert active_plan["status"] == "active"

    # 6. Create chapter plan and brief via DB
    cp = ChapterPlan(novel_id=novel_id, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(cp)
    await db.flush()
    brief = ChapterBrief(
        novel_id=novel_id, chapter_plan_id=cp.id,
        brief_json={"writing_goal": "完成本章剧情推进"},
        length_contract_json={"target_words": 10, "min_words": 1, "max_words": 100},
        status="ready",
    )
    db.add(brief)
    await db.commit()

    # 7. Writing run → completed
    ws = WritingService(
        db=db, user_id=1, novel_id=novel_id,
        generator=FakePhase3WritingGenerator(),
        gate_agent=FakeQualityGateAgent(),
    )
    run = await ws.create_writing_run(
        brief_id=brief.id, plot_plan_revision_id=active_plan["id"],
        author_input="本次必须让证人活着离开",
    )
    assert run.status == "completed"
    assert run.context_snapshot_json["plot_plan_revision_id"] == active_plan["id"]

    # 8. Writing run → decision_required
    conflicting_ws = WritingService(
        db=db, user_id=1, novel_id=novel_id,
        generator=FakePhase3WritingGenerator(draft_result=decision_required_result()),
        gate_agent=FakeQualityGateAgent(),
    )
    conflicting_run = await conflicting_ws.create_writing_run(
        brief_id=brief.id, plot_plan_revision_id=active_plan["id"],
    )
    assert conflicting_run.status == "decision_required"
    assert conflicting_run.decision_id is not None

    # 9. Get decision
    pp_svc = PlotPlanningService(db=db, user_id=1, novel_id=novel_id)
    decision = await pp_svc.get_decision(conflicting_run.decision_id)
    assert len(decision.options_json) in (2, 3)
    assert decision.recommended_index is not None

    # 10. Choose decision
    original_unaffected = "不越过冲突点的部分正文"
    revision_generator = FakePhase3WritingGenerator(
        revision=LocalRevisionOutput(
            candidate_content=f"开头不变。{original_unaffected}。结尾不变。",
            scope={"type": "paragraph", "start": 2, "end": 2},
            diff={"removed": ["旧"], "added": ["新"]},
            plan_patch={"progression": [{"order": 1, "purpose": "调整"}]},
            expanded_scope=False, expansion_reason="",
        )
    )
    pp_svc_rev = PlotPlanningService(db=db, user_id=1, novel_id=novel_id, generator=revision_generator)
    resolved_decision, new_plan, draft_revision, resolved_run = await pp_svc_rev.choose_decision(
        decision.id, option_index=decision.recommended_index,
    )
    assert resolved_decision.status == "resolved"
    assert draft_revision.status == "candidate"
    assert original_unaffected in draft_revision.candidate_content
    assert new_plan.version == active_plan["version"] + 1

    # 11. Accept run (update status since choose_decision resolves but doesn't set completed)
    await db.refresh(conflicting_run)
    conflicting_run.status = "completed"
    await db.flush()
    chapter_obj, extraction = await conflicting_ws.accept_writing_run(conflicting_run.id)
    assert chapter_obj.status == "draft"

    # 12. Publish the chapter via API
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_obj.id}/publish",
        headers=headers, json={},
    )
    assert resp.status_code == 200
    published = resp.json()["data"]
    assert published["status"] == "locked"

    # 13. Try to update locked chapter → 400
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/chapters/{published['id']}",
        headers=headers, json={"content": "改写"},
    )
    assert resp.status_code == 400

    # 14. Generate next chapter → context includes the new published chapter
    from app.services.context_package_service import ContextPackageService
    from app.core.database import async_session_factory
    async with async_session_factory() as fresh_db:
        ctx = await ContextPackageService(fresh_db, user_id=1, novel_id=novel_id).build_for_brief(
            brief_id=brief.id, plot_plan_revision_id=active_plan["id"],
        )
    assert published["id"] in ctx["snapshot"]["published_chapter_ids"]


# ===== Task 8: Exception path tests =====


@pytest.mark.asyncio
async def test_foundation_update_keeps_locked_content_unchanged(client, novel_and_headers, db):
    novel, headers = novel_and_headers
    novel_id = novel["id"]

    resp = await client.put(
        f"/api/v1/novels/{novel_id}/author-foundation",
        headers=headers,
        json={"outline": "大纲", "current_intent": "意图", "stage_goal": "目标", "constraints_json": {}},
    )
    assert resp.status_code == 200

    chapter = await create_locked_chapter(client, novel_id, headers, "不可修改的锁定内容")

    resp = await client.put(
        f"/api/v1/novels/{novel_id}/author-foundation",
        headers=headers,
        json={"stage_goal": "全新目标"},
    )
    assert resp.status_code == 200

    resp = await client.get(
        f"/api/v1/novels/{novel_id}/chapters/{chapter['id']}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["content"] == "不可修改的锁定内容"


@pytest.mark.asyncio
async def test_cross_user_planning_returns_404(client):
    resp = await client.post("/api/v1/auth/register", json={"username": "e2e_a", "password": "password123"})
    token_a = resp.json()["data"]["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    resp = await client.post("/api/v1/auth/register", json={"username": "e2e_b", "password": "password123"})
    token_b = resp.json()["data"]["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    resp = await client.post("/api/v1/novels", headers=headers_a, json={"title": "A的小说"})
    novel_a = resp.json()["data"]

    resp = await client.get(f"/api/v1/novels/{novel_a['id']}/author-foundation", headers=headers_b)
    assert resp.status_code == 404

    resp = await client.post(
        f"/api/v1/novels/{novel_a['id']}/plot-units",
        headers=headers_b,
        json={"title": "hack", "scope_type": "volume", "start_position": 1, "end_position": 1},
    )
    assert resp.status_code == 404

    resp = await client.get(f"/api/v1/novels/{novel_a['id']}/plot-units", headers=headers_b)
    assert resp.status_code == 404
