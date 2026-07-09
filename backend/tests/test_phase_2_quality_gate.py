"""Tests for Quality Gate Phase 2: RepairLog, PendingRepair models and WritingRun extensions."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.quality_gate import FakeQualityGateAgent, CheckResult
from app.main import app
from app.models.writing import RepairLog, PendingRepair, WritingRun
from app.repositories.quality_gate_repo import RepairLogRepo, PendingRepairRepo
from app.services.quality_gate_service import QualityGateService


async def _register_headers(client, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_novel(client, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/api/v1/novels",
        headers=headers,
        json={"title": "写作测试小说", "description": "用于测试自主写作闭环", "genre": "古风权谋", "style_guide": "第三人称有限视角"},
    )
    assert response.status_code == 200
    return response.json()["data"]


@pytest.fixture
async def novel_and_headers(client):
    headers = await _register_headers(client, "quality_gate_user")
    novel = await _create_novel(client, headers)
    return novel, headers


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


@pytest.mark.asyncio
async def test_repair_log_repo_create_and_list(db):
    repo = RepairLogRepo(db)
    log = await repo.create(1, 1, {
        "issue_type": "style",
        "description": "风格修复",
        "location": "第1段",
        "old_text": "旧文本",
        "new_text": "新文本",
    })
    assert log.id is not None
    logs = await repo.list_by_writing_run(1)
    assert len(logs) == 1
    assert logs[0].issue_type == "style"


@pytest.mark.asyncio
async def test_pending_repair_repo_create_and_list(db):
    repo = PendingRepairRepo(db)
    repair = await repo.create(1, 1, 1, {
        "issue_type": "character_choice",
        "description": "角色选择",
        "location": "第3段",
        "context": "原文",
        "options": [{"label": "A", "summary": "方案A"}],
        "intent_type": "choice",
    })
    assert repair.id is not None
    repairs = await repo.list_pending_by_writing_run(1)
    assert len(repairs) == 1
    assert repairs[0].status == "pending"


@pytest.mark.asyncio
async def test_pending_repair_update_status(db):
    repo = PendingRepairRepo(db)
    repair = await repo.create(1, 1, 1, {
        "issue_type": "character_choice",
        "description": "角色选择",
        "location": "第3段",
        "context": "原文",
        "intent_type": "choice",
    })
    updated = await repo.update_status(repair.id, "applied")
    assert updated.status == "applied"


@pytest.mark.asyncio
async def test_fake_quality_gate_returns_all_passed():
    agent = FakeQualityGateAgent()
    results = await agent.check("draft content", {}, {})
    assert isinstance(results, list)
    assert len(results) == 6
    for r in results:
        assert r.passed is True
        assert r.severity == "auto_fixable"


@pytest.mark.asyncio
async def test_fake_quality_gate_with_story_data():
    agent = FakeQualityGateAgent()
    brief = {"plot_task": "主角发现真相"}
    context = {"characters": [{"name": "张三", "personality": "谨慎"}]}
    results = await agent.check("故事正文内容", brief, context)
    assert all(r.passed for r in results)


@pytest.mark.asyncio
async def test_quality_gate_service_all_pass(db):
    """全部通过时，不产生 RepairLog 和 PendingRepair。"""
    from app.models.writing import WritingRun
    run = WritingRun(novel_id=1, chapter_brief_id=1, context_package_id=1, status="running", draft_content="test", word_count=4)
    db.add(run)
    await db.flush()
    svc = QualityGateService(db=db, agent=FakeQualityGateAgent())
    result = await svc.run(run, {}, {})
    assert result["gated"] is True
    assert result["has_pending_repairs"] is False
    logs_repo = RepairLogRepo(db)
    logs = await logs_repo.list_by_writing_run(run.id)
    assert len(logs) == 0
    pend_repo = PendingRepairRepo(db)
    repairs = await pend_repo.list_by_writing_run(run.id)
    assert len(repairs) == 0
    await db.rollback()


@pytest.mark.asyncio
async def test_quality_gate_service_no_agent(db):
    """不传 agent 时使用 FakeQualityGateAgent（默认行为）。"""
    from app.models.writing import WritingRun
    run = WritingRun(novel_id=1, chapter_brief_id=1, context_package_id=1, status="running", draft_content="test", word_count=4)
    db.add(run)
    await db.flush()
    svc = QualityGateService(db=db)
    result = await svc.run(run, {}, {})
    assert result["gated"] is True
    await db.rollback()


@pytest.mark.asyncio
async def test_quality_gate_in_writing_flow(client, novel_and_headers):
    """写作流程中质量门禁自动执行。"""
    novel, headers = novel_and_headers
    novel_id = novel["id"]

    # Generate blueprint
    bp_resp = await client.post(
        f"/api/v1/novels/{novel_id}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    bp_id = bp_resp.json()["data"]["id"]
    await client.put(f"/api/v1/novels/{novel_id}/blueprints/{bp_id}/activate", headers=headers)

    # Generate chapter plan
    plan_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-plans/next/generate",
        headers=headers,
    )
    plan_id = plan_resp.json()["data"]["id"]

    # Generate chapter brief
    brief_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-briefs/generate",
        headers=headers,
        json={"chapter_plan_id": plan_id},
    )
    brief_id = brief_resp.json()["data"]["id"]

    # Create writing run
    run_resp = await client.post(
        f"/api/v1/novels/{novel_id}/writing-runs",
        headers=headers,
        json={"chapter_brief_id": brief_id},
    )
    assert run_resp.status_code == 200
    run = run_resp.json()["data"]
    assert "gated" in run
