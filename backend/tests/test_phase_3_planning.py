"""Tests for Phase 3 planning contracts: VolumeArc, PlanVersion, ReviewIssue."""

import pytest

from app.models.planning import VolumeArc, PlanVersion, ReviewIssue
from app.schemas.planning import VolumeArcOut, PlanVersionOut, ReviewIssueOut


@pytest.mark.asyncio
async def test_volume_arc_creation(db):
    """VolumeArc 可以创建并读取所有字段。"""
    arc = VolumeArc(
        novel_id=1,
        blueprint_id=1,
        order_index=0,
        title="第一卷：觉醒",
        goal="主角发现自身力量并决定抗争",
        start_state="主角平凡无奇",
        end_state="主角踏上修行之路",
        key_events=["遭遇神秘老者", "觉醒灵根", "击败小镇恶霸"],
        pacing_notes="前期慢热，后三分之一加速",
        foreshadowing_plan=[{"item": "神秘玉佩", "planted_chapter": 1}],
        status="draft",
    )
    db.add(arc)
    await db.flush()
    result = await db.get(VolumeArc, arc.id)
    assert result is not None
    assert result.novel_id == 1
    assert result.blueprint_id == 1
    assert result.order_index == 0
    assert result.title == "第一卷：觉醒"
    assert result.goal == "主角发现自身力量并决定抗争"
    assert result.start_state == "主角平凡无奇"
    assert result.end_state == "主角踏上修行之路"
    assert result.key_events == ["遭遇神秘老者", "觉醒灵根", "击败小镇恶霸"]
    assert result.pacing_notes == "前期慢热，后三分之一加速"
    assert result.foreshadowing_plan == [{"item": "神秘玉佩", "planted_chapter": 1}]
    assert result.status == "draft"


@pytest.mark.asyncio
async def test_volume_arc_nullable_blueprint_id(db):
    """VolumeArc.blueprint_id 可为 None。"""
    arc = VolumeArc(
        novel_id=1,
        blueprint_id=None,
        order_index=1,
        title="第二卷",
        goal="",
        start_state="",
        end_state="",
        key_events=[],
        pacing_notes="",
        foreshadowing_plan=[],
    )
    db.add(arc)
    await db.flush()
    result = await db.get(VolumeArc, arc.id)
    assert result is not None
    assert result.blueprint_id is None
    assert result.status == "draft"


@pytest.mark.asyncio
async def test_volume_arc_schema_serialization(db):
    """VolumeArcOut 可从 ORM 对象序列化。"""
    arc = VolumeArc(
        novel_id=1,
        blueprint_id=None,
        order_index=0,
        title="测试卷",
        goal="目标",
        start_state="开始",
        end_state="结束",
        key_events=["事件A"],
        pacing_notes="节奏",
        foreshadowing_plan={"items": []},
        status="active",
    )
    db.add(arc)
    await db.flush()
    out = VolumeArcOut.model_validate(arc)
    assert out.id == arc.id
    assert out.novel_id == 1
    assert out.title == "测试卷"
    assert out.status == "active"
    assert out.key_events == ["事件A"]
    assert out.foreshadowing_plan == {"items": []}


@pytest.mark.asyncio
async def test_plan_version_creation(db):
    """PlanVersion 可以创建并读取所有字段。"""
    pv = PlanVersion(
        novel_id=1,
        plan_type="blueprint",
        plan_id=1,
        version=1,
        change_reason="初版蓝图",
        impact_scope="全局设定",
        snapshot_json={"core_promise": "测试"},
        status="current",
    )
    db.add(pv)
    await db.flush()
    result = await db.get(PlanVersion, pv.id)
    assert result is not None
    assert result.novel_id == 1
    assert result.plan_type == "blueprint"
    assert result.plan_id == 1
    assert result.version == 1
    assert result.change_reason == "初版蓝图"
    assert result.impact_scope == "全局设定"
    assert result.snapshot_json == {"core_promise": "测试"}
    assert result.status == "current"


@pytest.mark.asyncio
async def test_plan_version_default_status(db):
    """PlanVersion 默认 status 为 current，version 默认 1。"""
    pv = PlanVersion(
        novel_id=1,
        plan_type="chapter_plan",
        plan_id=2,
        change_reason="更新",
        impact_scope="第3章",
        snapshot_json={},
    )
    db.add(pv)
    await db.flush()
    result = await db.get(PlanVersion, pv.id)
    assert result.version == 1
    assert result.status == "current"


@pytest.mark.asyncio
async def test_plan_version_schema_serialization(db):
    """PlanVersionOut 可从 ORM 对象序列化。"""
    pv = PlanVersion(
        novel_id=1,
        plan_type="volume_arc",
        plan_id=1,
        version=3,
        change_reason="卷弧修订",
        impact_scope="第一卷",
        snapshot_json={"title": "第一卷"},
        status="archived",
    )
    db.add(pv)
    await db.flush()
    out = PlanVersionOut.model_validate(pv)
    assert out.id == pv.id
    assert out.plan_type == "volume_arc"
    assert out.version == 3
    assert out.status == "archived"
    assert out.snapshot_json == {"title": "第一卷"}


@pytest.mark.asyncio
async def test_review_issue_creation(db):
    """ReviewIssue 可以创建并读取所有字段。"""
    issue = ReviewIssue(
        novel_id=1,
        writing_run_id=1,
        issue_type="character",
        severity="needs_intent",
        location="第2段",
        description="角色反应与前期人设不一致",
        related_memory="角色档案#张三",
        suggestion="调整为更谨慎的语气",
        acceptance_blocking=True,
        status="open",
    )
    db.add(issue)
    await db.flush()
    result = await db.get(ReviewIssue, issue.id)
    assert result is not None
    assert result.novel_id == 1
    assert result.writing_run_id == 1
    assert result.issue_type == "character"
    assert result.severity == "needs_intent"
    assert result.location == "第2段"
    assert result.description == "角色反应与前期人设不一致"
    assert result.related_memory == "角色档案#张三"
    assert result.suggestion == "调整为更谨慎的语气"
    assert result.acceptance_blocking is True
    assert result.status == "open"


@pytest.mark.asyncio
async def test_review_issue_nullable_writing_run_id(db):
    """ReviewIssue.writing_run_id 可为 None（草稿尚未分配到 run 时）。"""
    issue = ReviewIssue(
        novel_id=1,
        writing_run_id=None,
        issue_type="continuity",
        severity="auto_fixable",
        location="全文",
        description="时间线矛盾",
        suggestion="修正第3章时间引用",
    )
    db.add(issue)
    await db.flush()
    result = await db.get(ReviewIssue, issue.id)
    assert result is not None
    assert result.writing_run_id is None
    assert result.acceptance_blocking is True
    assert result.status == "open"


@pytest.mark.asyncio
async def test_review_issue_schema_serialization(db):
    """ReviewIssueOut 可从 ORM 对象序列化。"""
    issue = ReviewIssue(
        novel_id=1,
        writing_run_id=None,
        issue_type="style",
        severity="auto_fixable",
        location="第1段",
        description="风格过于口语化",
        related_memory=None,
        suggestion="改为书面语",
        acceptance_blocking=False,
        status="resolved",
    )
    db.add(issue)
    await db.flush()
    out = ReviewIssueOut.model_validate(issue)
    assert out.id == issue.id
    assert out.writing_run_id is None
    assert out.issue_type == "style"
    assert out.severity == "auto_fixable"
    assert out.acceptance_blocking is False
    assert out.status == "resolved"
