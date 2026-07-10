import pytest
from pydantic import ValidationError

from app.ai.plot_planning import (
    ConflictOutput,
    DecisionOption,
    DraftGenerationOutput,
)
from app.ai.writer import FakePhase3WritingGenerator
from app.core.exceptions import NotFound
from app.models.novel import Novel, Chapter
from app.models.plot_planning import (
    AuthorFoundation,
    AuthorFoundationRevision,
    PlotUnit,
    PlotPlanRevision,
    PlanningDecision,
)
from app.models.user import User
from app.models.writing import ChapterPlan, ChapterBrief
from app.schemas.plot_planning import ChooseDecisionRequest


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
