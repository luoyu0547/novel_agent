import pytest
from pydantic import ValidationError

from app.ai.plot_planning import (
    ConflictOutput,
    DecisionOption,
    DraftGenerationOutput,
)
from app.ai.writer import FakePhase3WritingGenerator
from app.models.plot_planning import (
    AuthorFoundation,
    AuthorFoundationRevision,
    PlotUnit,
    PlotPlanRevision,
    PlanningDecision,
)
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
