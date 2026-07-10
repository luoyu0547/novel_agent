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
async def test_writing_run_v2_extension_fields(db):
    """WritingRun 支持 v2 扩展字段：mode、word counts、input_snapshot、agent_notes、self_check、plan_version_ids。"""
    run = WritingRun(
        novel_id=1,
        chapter_brief_id=1,
        context_package_id=1,
        status="completed",
        draft_content="test",
        word_count=4,
        mode="deep",
        target_word_count=3000,
        min_word_count=2000,
        max_word_count=5000,
        input_snapshot={"blueprint_version": 1, "volume_arc_id": 2},
        agent_notes="自我评估：结构完整，节奏偏快",
        self_check={"passed": True, "notes": "自查通过"},
        plan_version_ids=[1, 2, 3],
    )
    db.add(run)
    await db.flush()
    result = await db.get(WritingRun, run.id)
    assert result.mode == "deep"
    assert result.target_word_count == 3000
    assert result.min_word_count == 2000
    assert result.max_word_count == 5000
    assert result.input_snapshot == {"blueprint_version": 1, "volume_arc_id": 2}
    assert result.agent_notes == "自我评估：结构完整，节奏偏快"
    assert result.self_check == {"passed": True, "notes": "自查通过"}
    assert result.plan_version_ids == [1, 2, 3]


@pytest.mark.asyncio
async def test_writing_run_v2_default_values(db):
    """WritingRun v2 扩展字段有合理默认值。"""
    run = WritingRun(
        novel_id=1,
        chapter_brief_id=1,
        context_package_id=1,
        status="running",
        draft_content="",
        word_count=0,
    )
    db.add(run)
    await db.flush()
    result = await db.get(WritingRun, run.id)
    assert result.mode == "standard"
    assert result.target_word_count == 0
    assert result.min_word_count == 0
    assert result.max_word_count == 0
    assert result.input_snapshot == {}
    assert result.agent_notes == ""
    assert result.self_check == {}
    assert result.plan_version_ids == []


@pytest.mark.asyncio
async def test_pending_repair_nullable_chapter_id(db):
    """PendingRepair.chapter_id 可为 None（草稿尚未被接受到真实章节时），且关联真实 WritingRun。"""
    run = WritingRun(
        novel_id=1,
        chapter_brief_id=1,
        context_package_id=1,
        target_chapter_id=None,
        status="completed",
        draft_content="草稿正文",
        word_count=4,
    )
    db.add(run)
    await db.flush()
    assert run.id is not None

    repair = PendingRepair(
        novel_id=1,
        chapter_id=None,
        writing_run_id=run.id,
        issue_type="character_choice",
        description="角色抉择方向",
        location="第3段",
        context="角色面临抉择的原文片段",
        options=[{"label": "方案A", "summary": "果断"}],
        intent_type="choice",
        status="pending",
    )
    db.add(repair)
    await db.flush()

    persisted_repair = await db.get(PendingRepair, repair.id)
    assert persisted_repair is not None
    assert persisted_repair.chapter_id is None
    assert persisted_repair.writing_run_id == run.id
    assert persisted_repair.status == "pending"

    persisted_run = await db.get(WritingRun, run.id)
    assert persisted_run is not None
    assert persisted_run.target_chapter_id is None


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
    assert len(results) == 7
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


@pytest.mark.asyncio
async def test_get_repairs_endpoint(client, novel_and_headers):
    novel, headers = novel_and_headers
    novel_id = novel["id"]

    bp_resp = await client.post(
        f"/api/v1/novels/{novel_id}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    bp_id = bp_resp.json()["data"]["id"]
    await client.put(f"/api/v1/novels/{novel_id}/blueprints/{bp_id}/activate", headers=headers)
    plan_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-plans/next/generate", headers=headers)
    plan_id = plan_resp.json()["data"]["id"]
    brief_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-briefs/generate", headers=headers,
        json={"chapter_plan_id": plan_id})
    brief_id = brief_resp.json()["data"]["id"]
    run_resp = await client.post(
        f"/api/v1/novels/{novel_id}/writing-runs", headers=headers,
        json={"chapter_brief_id": brief_id})
    run_id = run_resp.json()["data"]["id"]

    resp = await client.get(
        f"/api/v1/novels/{novel_id}/writing-runs/{run_id}/repairs", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "repair_logs" in data
    assert "pending_repairs" in data


# ---------------------------------------------------------------------------
# Phase 2 real quality gate checks (Task 2)
# ---------------------------------------------------------------------------


from app.ai.quality_gate import AGENT_TYPES, BaseQualityGateAgent  # noqa: E402


class ScriptedFakeAgent(BaseQualityGateAgent):
    """Returns a fixed list of CheckResults for deterministic tests."""

    def __init__(self, results):
        self._results = results

    async def check(self, draft: str, brief: dict, context_package: dict) -> list:
        return list(self._results)


class RaisingFakeAgent(BaseQualityGateAgent):
    """Simulates a provider/parse failure."""

    def __init__(self, exc: Exception):
        self._exc = exc

    async def check(self, draft: str, brief: dict, context_package: dict) -> list:
        raise self._exc


class CountingFakeGenerator:
    """Wraps FakeWritingGenerator and counts generate_draft calls."""

    def __init__(self):
        from app.ai.writer import FakeWritingGenerator

        self._inner = FakeWritingGenerator()
        self.call_count = 0

    async def generate_draft(self, context_package: dict) -> str:
        self.call_count += 1
        return await self._inner.generate_draft(context_package)

    async def generate_blueprint(self, *a, **kw):
        return await self._inner.generate_blueprint(*a, **kw)

    async def generate_chapter_plan(self, *a, **kw):
        return await self._inner.generate_chapter_plan(*a, **kw)

    async def generate_chapter_brief(self, *a, **kw):
        return await self._inner.generate_chapter_brief(*a, **kw)


async def _seed_writing_setup(db):
    """Create a user, novel, chapter plan and brief for WritingService tests."""
    from app.models.user import User
    from app.models.novel import Novel
    from app.models.writing import ChapterPlan, ChapterBrief

    user = User(username="gate_runner", hashed_password="x")
    db.add(user)
    await db.flush()
    novel = Novel(user_id=user.id, title="门禁测试", description="", genre="古风", style_guide="第三人称")
    db.add(novel)
    await db.flush()
    plan = ChapterPlan(novel_id=novel.id, position=1, status="ready", content_json={"chapter_title": "第一章"})
    db.add(plan)
    await db.flush()
    brief = ChapterBrief(
        novel_id=novel.id,
        chapter_plan_id=plan.id,
        status="ready",
        brief_json={"writing_goal": "推进剧情", "acceptance_criteria": "完成剧情任务"},
        length_contract_json={"target_words": 100, "min_words": 50, "max_words": 5000},
    )
    db.add(brief)
    await db.flush()
    return user.id, novel.id, brief.id


@pytest.mark.asyncio
async def test_quality_gate_service_needs_intent_and_auto_fixable(db):
    """One needs_intent character issue + one auto_fixable style issue creates the
    correct repair records, keeps location/context, and returns has_pending_repairs."""
    from app.models.writing import WritingRun

    run = WritingRun(
        novel_id=1,
        chapter_brief_id=1,
        context_package_id=1,
        status="running",
        draft_content="原文片段ABC剩余正文",
        word_count=10,
    )
    db.add(run)
    await db.flush()

    results = [
        CheckResult(
            passed=False,
            issue_type="character",
            severity="needs_intent",
            description="角色反应与既定人设不符",
            location="第3段",
            context="主角突然表现出与谨慎人设相悖的冲动",
            options=[{"label": "方案A", "summary": "保持谨慎"}, {"label": "方案B", "summary": "解释冲动原因"}],
            intent_type="choice",
        ),
        CheckResult(
            passed=False,
            issue_type="style",
            severity="auto_fixable",
            fix_strategy="local_replace",
            fixed_text="修正后的文风片段",
            fix_description="替换口语化表达",
            location="原文片段ABC",
        ),
    ]
    svc = QualityGateService(db=db, agent=ScriptedFakeAgent(results))
    result = await svc.run(run, {}, {})

    assert result["gated"] is True
    assert result["has_pending_repairs"] is True

    # PendingRepair keeps character issue location/context/options/intent_type
    pend_repo = PendingRepairRepo(db)
    repairs = await pend_repo.list_by_writing_run(run.id)
    assert len(repairs) == 1
    pr = repairs[0]
    assert pr.issue_type == "character"
    assert pr.location == "第3段"
    assert pr.context == "主角突然表现出与谨慎人设相悖的冲动"
    assert pr.intent_type == "choice"
    assert pr.options == [{"label": "方案A", "summary": "保持谨慎"}, {"label": "方案B", "summary": "解释冲动原因"}]

    # RepairLog records the local replace and draft is updated
    log_repo = RepairLogRepo(db)
    logs = await log_repo.list_by_writing_run(run.id)
    assert len(logs) == 1
    assert logs[0].issue_type == "style"
    refreshed = await db.get(WritingRun, run.id)
    assert refreshed.draft_content == "修正后的文风片段剩余正文"

    # ReviewIssue persisted for every failed check
    from app.models.planning import ReviewIssue
    from sqlalchemy import select

    issues = (await db.execute(select(ReviewIssue).where(ReviewIssue.writing_run_id == run.id))).scalars().all()
    assert len(issues) == 2
    issue_types = {i.issue_type for i in issues}
    assert issue_types == {"character", "style"}
    await db.rollback()


@pytest.mark.asyncio
async def test_parse_check_results_contract():
    """Parsed results always carry an allowed issue type and severity."""
    from app.ai.quality_agents import parse_check_results

    raw = '''
    [
        {"passed": true, "severity": "auto_fixable", "extra_field": "ignored"},
        {"passed": false, "severity": "needs_intent", "location": "第2段", "description": "问题", "unknown": 1}
    ]
    '''
    results = parse_check_results(raw, "continuity")
    assert len(results) == 2
    for r in results:
        assert r.issue_type == "continuity"
        assert r.issue_type in AGENT_TYPES
        assert r.severity in ("auto_fixable", "needs_intent")
    assert results[0].passed is True
    assert results[1].passed is False


@pytest.mark.asyncio
async def test_parse_check_results_malformed_raises():
    """A malformed model response raises so the service can convert it to a failed gate."""
    from app.ai.quality_agents import parse_check_results

    # not JSON
    try:
        parse_check_results("not json at all", "style")
        assert False, "expected raise on non-JSON"
    except Exception:
        pass

    # invalid severity
    try:
        parse_check_results('[{"passed": false, "severity": "bogus"}]', "style")
        assert False, "expected raise on invalid severity"
    except Exception:
        pass


@pytest.mark.asyncio
async def test_deepseek_quality_gate_agent_has_seven_checkers():
    """The real agent wires one checker per AGENT_TYPE, invoked sequentially."""
    from app.ai.quality_agents import DeepSeekQualityGateAgent

    agent = DeepSeekQualityGateAgent()
    assert len(agent.checkers) == len(AGENT_TYPES)
    wired_types = {c.issue_type for c in agent.checkers}
    assert wired_types == set(AGENT_TYPES)


@pytest.mark.asyncio
async def test_quality_gate_service_provider_failure(db):
    """Provider/parse failure leaves the draft available with gated=False and a diagnostic."""
    from app.models.writing import WritingRun

    run = WritingRun(
        novel_id=1,
        chapter_brief_id=1,
        context_package_id=1,
        status="running",
        draft_content="草稿正文应保留",
        word_count=6,
    )
    db.add(run)
    await db.flush()

    svc = QualityGateService(db=db, agent=RaisingFakeAgent(RuntimeError("deepseek timeout")))
    result = await svc.run(run, {}, {})

    assert result["gated"] is False
    assert result["has_pending_repairs"] is False
    assert result["rewrite_needed"] is False
    refreshed = await db.get(WritingRun, run.id)
    assert refreshed.gated is False
    # draft preserved
    assert refreshed.draft_content == "草稿正文应保留"
    # diagnostic recorded
    assert refreshed.gate_result_json.get("error")
    await db.rollback()


@pytest.mark.asyncio
async def test_writing_run_three_iteration_limit(db):
    """The auto-fix rewrite loop is bounded to 3 iterations and terminates."""
    from app.services.writing_service import WritingService

    user_id, novel_id, brief_id = await _seed_writing_setup(db)

    gen = CountingFakeGenerator()
    always_rewrite = ScriptedFakeAgent(
        [CheckResult(passed=False, issue_type="style", severity="auto_fixable", fix_strategy="full_rewrite", fix_description="重写")]
    )
    svc = WritingService(db=db, user_id=user_id, novel_id=novel_id, generator=gen, gate_agent=always_rewrite)
    run = await svc.create_writing_run(brief_id)

    # bounded: 1 initial draft + at most 2 rewrites == 3 generations
    assert gen.call_count == 3
    assert run.status == "completed"
    assert run.draft_content  # draft available
    await db.rollback()


@pytest.mark.asyncio
async def test_writing_run_all_pass_no_rewrite(db):
    """All-pass quality gate does not trigger any rewrite."""
    from app.services.writing_service import WritingService

    user_id, novel_id, brief_id = await _seed_writing_setup(db)

    gen = CountingFakeGenerator()
    svc = WritingService(db=db, user_id=user_id, novel_id=novel_id, generator=gen, gate_agent=FakeQualityGateAgent())
    run = await svc.create_writing_run(brief_id)

    assert gen.call_count == 1
    assert run.status == "completed"
    assert run.gated is True
    assert run.has_pending_repairs is False
    await db.rollback()


# ---------------------------------------------------------------------------
# Task 3: RepairService — apply intent to writing drafts
# ---------------------------------------------------------------------------


async def _seed_repair_setup(db):
    """Create user, novel, and WritingRun for RepairService tests."""
    from app.models.user import User
    from app.models.novel import Novel
    from app.models.writing import WritingRun

    user = User(username="repair_tester", hashed_password="x")
    db.add(user)
    await db.flush()
    novel = Novel(user_id=user.id, title="修复测试", description="", genre="古风", style_guide="第三人称")
    db.add(novel)
    await db.flush()
    run = WritingRun(
        novel_id=novel.id,
        chapter_brief_id=1,
        context_package_id=1,
        status="completed",
        draft_content="这是第一段。这是特定段落。这是最后一段。",
        word_count=20,
        has_pending_repairs=True,
    )
    db.add(run)
    await db.flush()
    return user.id, novel.id, run.id


@pytest.mark.asyncio
async def test_repair_service_apply_choice_rewrites_draft(db):
    """apply with choice calls rewrite_fragment, updates WritingRun.draft_content, creates RepairLog."""
    from app.services.repair_service import RepairService
    from app.ai.writer import FakeWritingGenerator
    from app.repositories.quality_gate_repo import PendingRepairRepo, RepairLogRepo
    from app.models.writing import WritingRun

    user_id, novel_id, run_id = await _seed_repair_setup(db)

    pending_repo = PendingRepairRepo(db)
    location = "特定段落"
    repair = await pending_repo.create(novel_id, None, run_id, {
        "issue_type": "character_choice",
        "description": "角色抉择",
        "location": location,
        "context": "角色面临选择",
        "options": [{"label": "方案A", "summary": "保持谨慎"}, {"label": "方案B", "summary": "表现果断"}],
        "intent_type": "choice",
    })
    await db.commit()

    gen = FakeWritingGenerator()
    svc = RepairService(db=db, user_id=user_id, novel_id=novel_id, generator=gen)
    result = await svc.resolve(novel_id, repair.id, "apply", choice_index=0)

    assert result.status == "applied"

    run = await db.get(WritingRun, run_id)
    assert f"[{location}]" in run.draft_content

    log_repo = RepairLogRepo(db)
    logs = await log_repo.list_by_writing_run(run_id)
    assert len(logs) == 1
    assert logs[0].issue_type == "character_choice"
    assert logs[0].location == location
    assert logs[0].old_text == location
    assert logs[0].new_text == f"[{location}]"

    assert run.has_pending_repairs is False
    await db.rollback()


@pytest.mark.asyncio
async def test_repair_service_dismiss_leaves_draft_unchanged(db):
    """dismiss leaves draft unchanged, marks repair dismissed."""
    from app.services.repair_service import RepairService
    from app.ai.writer import FakeWritingGenerator
    from app.repositories.quality_gate_repo import PendingRepairRepo, RepairLogRepo
    from app.models.writing import WritingRun

    user_id, novel_id, run_id = await _seed_repair_setup(db)

    pending_repo = PendingRepairRepo(db)
    repair = await pending_repo.create(novel_id, None, run_id, {
        "issue_type": "character_choice",
        "description": "角色抉择",
        "location": "某段落",
        "context": "角色面临选择",
        "intent_type": "choice",
    })
    await db.commit()

    run_before = await db.get(WritingRun, run_id)
    original_draft = run_before.draft_content

    gen = FakeWritingGenerator()
    svc = RepairService(db=db, user_id=user_id, novel_id=novel_id, generator=gen)
    result = await svc.resolve(novel_id, repair.id, "dismiss")

    assert result.status == "dismissed"

    run_after = await db.get(WritingRun, run_id)
    assert run_after.draft_content == original_draft

    log_repo = RepairLogRepo(db)
    logs = await log_repo.list_by_writing_run(run_id)
    assert len(logs) == 0
    await db.rollback()


@pytest.mark.asyncio
async def test_resolve_repair_cross_novel_404(client, novel_and_headers, db):
    """Cross-novel repair returns 404."""
    from app.models.writing import WritingRun, PendingRepair

    novel, headers = novel_and_headers
    novel_id = novel["id"]

    other_headers = await _register_headers(client, "cross_user_resolve")
    other_resp = await client.post(
        "/api/v1/novels",
        headers=other_headers,
        json={"title": "跨小说测试", "description": "", "genre": "古风"},
    )
    other_novel_id = other_resp.json()["data"]["id"]

    run = WritingRun(
        novel_id=other_novel_id,
        chapter_brief_id=1,
        context_package_id=1,
        status="completed",
        draft_content="其他小说草稿",
        word_count=6,
        has_pending_repairs=True,
    )
    db.add(run)
    await db.flush()

    repair = PendingRepair(
        novel_id=other_novel_id,
        writing_run_id=run.id,
        issue_type="character_choice",
        description="测试",
        location="段落",
        context="上下文",
        intent_type="choice",
        status="pending",
    )
    db.add(repair)
    await db.commit()

    resp = await client.put(
        f"/api/v1/novels/{novel_id}/writing/repairs/{repair.id}/resolve",
        headers=headers,
        json={"action": "apply", "choice_index": 0},
    )
    assert resp.status_code == 404
    assert "修复项不存在" in resp.json()["message"]


@pytest.mark.asyncio
async def test_resolve_repair_already_resolved_400(client, novel_and_headers, db):
    """Already resolved repair returns 400."""
    from app.models.writing import WritingRun, PendingRepair

    novel, headers = novel_and_headers
    novel_id = novel["id"]

    run = WritingRun(
        novel_id=novel_id,
        chapter_brief_id=1,
        context_package_id=1,
        status="completed",
        draft_content="草稿正文",
        word_count=4,
        has_pending_repairs=True,
    )
    db.add(run)
    await db.flush()

    repair = PendingRepair(
        novel_id=novel_id,
        writing_run_id=run.id,
        issue_type="character_choice",
        description="已处理",
        location="段落",
        context="上下文",
        intent_type="choice",
        status="applied",
    )
    db.add(repair)
    await db.commit()

    resp = await client.put(
        f"/api/v1/novels/{novel_id}/writing/repairs/{repair.id}/resolve",
        headers=headers,
        json={"action": "apply"},
    )
    assert resp.status_code == 400
    assert "已处理" in resp.json()["message"]


# ---------------------------------------------------------------------------
# Task 4: Post-accept extraction hook
# ---------------------------------------------------------------------------


class CountingFakeExtractionService:
    """Records calls to extract for assertion."""

    def __init__(self):
        self.call_count = 0
        self.captured_kwargs = None

    async def extract(self, novel_id: int, chapter_id: int, user_id: int) -> dict:
        self.call_count += 1
        self.captured_kwargs = dict(novel_id=novel_id, chapter_id=chapter_id, user_id=user_id)
        return {"chapter_summary": "fake", "pending_ids": [1, 2], "pending_count": 2}


class RaisingFakeExtractionService:
    """Simulates extraction failure."""

    async def extract(self, novel_id: int, chapter_id: int, user_id: int) -> dict:
        raise RuntimeError("extraction failed")


@pytest.mark.asyncio
async def test_accept_new_chapter_calls_extraction(db):
    """Accepting a new chapter invokes extraction with correct chapter_id."""
    from app.services.writing_service import WritingService
    from app.ai.writer import FakeWritingGenerator
    from app.ai.quality_gate import FakeQualityGateAgent

    user_id, novel_id, brief_id = await _seed_writing_setup(db)

    gen = FakeWritingGenerator()
    extractor = CountingFakeExtractionService()
    svc = WritingService(
        db=db, user_id=user_id, novel_id=novel_id,
        generator=gen, gate_agent=FakeQualityGateAgent(),
        extraction_service=extractor,
    )
    run = await svc.create_writing_run(brief_id)
    assert run.status == "completed"

    chapter, extraction = await svc.accept_writing_run(run.id)
    assert extractor.call_count == 1
    assert extractor.captured_kwargs["chapter_id"] == chapter.id
    assert extractor.captured_kwargs["novel_id"] == novel_id
    assert extractor.captured_kwargs["user_id"] == user_id
    assert extraction["pending_count"] == 2
    assert extraction["pending_ids"] == [1, 2]
    await db.rollback()


@pytest.mark.asyncio
async def test_accept_existing_chapter_calls_extraction(db):
    """Accepting into a target chapter invokes extraction with that chapter."""
    from app.services.writing_service import WritingService
    from app.ai.writer import FakeWritingGenerator
    from app.ai.quality_gate import FakeQualityGateAgent
    from app.models.novel import Chapter

    user_id, novel_id, brief_id = await _seed_writing_setup(db)

    # Pre-create a chapter
    existing = Chapter(novel_id=novel_id, title="已有章节", content="旧内容", summary="", status="draft")
    db.add(existing)
    await db.flush()

    gen = FakeWritingGenerator()
    extractor = CountingFakeExtractionService()
    svc = WritingService(
        db=db, user_id=user_id, novel_id=novel_id,
        generator=gen, gate_agent=FakeQualityGateAgent(),
        extraction_service=extractor,
    )
    run = await svc.create_writing_run(brief_id)
    run.target_chapter_id = existing.id
    await db.flush()

    chapter, extraction = await svc.accept_writing_run(run.id)
    assert chapter.id == existing.id
    assert extractor.call_count == 1
    assert extractor.captured_kwargs["chapter_id"] == existing.id
    await db.rollback()


@pytest.mark.asyncio
async def test_accept_extraction_failure_does_not_rollback_accept(db):
    """Extraction failure after accept does not undo the chapter acceptance."""
    from app.services.writing_service import WritingService
    from app.ai.writer import FakeWritingGenerator
    from app.ai.quality_gate import FakeQualityGateAgent
    from app.models.novel import Chapter
    from app.models.writing import WritingRun
    from sqlalchemy import select

    user_id, novel_id, brief_id = await _seed_writing_setup(db)

    gen = FakeWritingGenerator()
    extractor = RaisingFakeExtractionService()
    svc = WritingService(
        db=db, user_id=user_id, novel_id=novel_id,
        generator=gen, gate_agent=FakeQualityGateAgent(),
        extraction_service=extractor,
    )
    run = await svc.create_writing_run(brief_id)

    chapter, extraction = await svc.accept_writing_run(run.id)
    assert chapter.id is not None
    assert extraction["error"] is not None
    assert "extraction failed" in extraction["error"]
    assert extraction["pending_count"] == 0

    # Chapter is persisted
    persisted = await db.get(Chapter, chapter.id)
    assert persisted is not None
    assert persisted.content == run.draft_content

    # Run is accepted
    refreshed = await db.get(WritingRun, run.id)
    assert refreshed.status == "accepted"
    await db.rollback()


@pytest.mark.asyncio
async def test_accept_api_returns_extraction_info(client, novel_and_headers):
    """The accept endpoint returns extraction info in the response."""
    novel, headers = novel_and_headers
    novel_id = novel["id"]

    bp_resp = await client.post(
        f"/api/v1/novels/{novel_id}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    bp_id = bp_resp.json()["data"]["id"]
    await client.put(f"/api/v1/novels/{novel_id}/blueprints/{bp_id}/activate", headers=headers)
    plan_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-plans/next/generate", headers=headers)
    plan_id = plan_resp.json()["data"]["id"]
    brief_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-briefs/generate", headers=headers,
        json={"chapter_plan_id": plan_id})
    brief_id = brief_resp.json()["data"]["id"]
    run_resp = await client.post(
        f"/api/v1/novels/{novel_id}/writing-runs", headers=headers,
        json={"chapter_brief_id": brief_id})
    run_id = run_resp.json()["data"]["id"]

    resp = await client.put(
        f"/api/v1/novels/{novel_id}/writing-runs/{run_id}/accept",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "chapter" in data
    assert "extraction" in data
    assert "pending_ids" in data["extraction"]
    assert "pending_count" in data["extraction"]
    assert data["chapter"]["novel_id"] == novel_id
