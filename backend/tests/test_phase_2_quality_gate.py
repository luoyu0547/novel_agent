"""Tests for Quality Gate Phase 2: RepairLog, PendingRepair models and WritingRun extensions."""

import pytest

from app.models.writing import RepairLog, PendingRepair, WritingRun


@pytest.mark.asyncio
async def test_repair_log_creation(db):
    """RepairLog 可以创建和读取。"""
    log = RepairLog(
        novel_id=1,
        writing_run_id=1,
        issue_type="character",
        description="人设修正",
        location="第2段",
        old_text="原文本摘要",
        new_text="新文本摘要",
    )
    db.add(log)
    await db.flush()
    result = await db.get(RepairLog, log.id)
    assert result is not None
    assert result.issue_type == "character"


@pytest.mark.asyncio
async def test_pending_repair_creation(db):
    """PendingRepair 可以创建和读取。"""
    repair = PendingRepair(
        novel_id=1,
        chapter_id=1,
        writing_run_id=1,
        issue_type="character_choice",
        description="角色抉择方向",
        location="第3段",
        context="角色面临抉择的原文片段",
        options=[{"label": "方案A", "summary": "角色表现果断"}, {"label": "方案B", "summary": "角色表现犹豫"}],
        intent_type="choice",
        status="pending",
    )
    db.add(repair)
    await db.flush()
    result = await db.get(PendingRepair, repair.id)
    assert result is not None
    assert result.intent_type == "choice"
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_writing_run_has_gate_fields(db):
    """WritingRun 新增 gated 和 has_pending_repairs 字段。"""
    run = WritingRun(
        novel_id=1,
        chapter_brief_id=1,
        context_package_id=1,
        status="completed",
        draft_content="test",
        word_count=4,
        gated=True,
        has_pending_repairs=False,
    )
    db.add(run)
    await db.flush()
    result = await db.get(WritingRun, run.id)
    assert result.gated is True
    assert result.has_pending_repairs is False
