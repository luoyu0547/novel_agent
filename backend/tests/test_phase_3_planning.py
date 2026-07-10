"""Tests for Phase 3 planning contracts: VolumeArc, PlanVersion, ReviewIssue."""

import pytest

from app.models.planning import VolumeArc, PlanVersion, ReviewIssue
from app.models.writing import ChapterPlan
from app.schemas.planning import VolumeArcOut, PlanVersionOut, ReviewIssueOut
from app.schemas.writing import ChapterPlanOut


# ── Existing model/schema creation tests (unchanged) ──────────────────────


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


# ── ChapterPlan extended fields (new for Task 6) ────────────────────────────


@pytest.mark.asyncio
async def test_chapter_plan_extended_fields(db):
    """ChapterPlan 新字段可正确创建和读取。"""
    plan = ChapterPlan(
        novel_id=1,
        blueprint_id=2,
        volume_arc_id=3,
        position=1,
        version=2,
        status="ready",
        content_json={"chapter_title": "测试章"},
        emotional_effect="紧张悬疑",
        target_word_count=4000,
        foreshadowing_tasks={"hint": "玉佩来历", "plant_chapter": 5},
        acceptance_criteria="字数达标，冲突充分展开",
    )
    db.add(plan)
    await db.flush()
    result = await db.get(ChapterPlan, plan.id)
    assert result is not None
    assert result.blueprint_id == 2
    assert result.volume_arc_id == 3
    assert result.version == 2
    assert result.emotional_effect == "紧张悬疑"
    assert result.target_word_count == 4000
    assert result.foreshadowing_tasks == {"hint": "玉佩来历", "plant_chapter": 5}
    assert result.acceptance_criteria == "字数达标，冲突充分展开"


@pytest.mark.asyncio
async def test_chapter_plan_default_version(db):
    """ChapterPlan 默认 version=1，foreshadowing_tasks={}, acceptance_criteria=""。"""
    plan = ChapterPlan(
        novel_id=1,
        position=1,
        content_json={},
    )
    db.add(plan)
    await db.flush()
    result = await db.get(ChapterPlan, plan.id)
    assert result.version == 1
    assert result.foreshadowing_tasks == {}
    assert result.acceptance_criteria == ""
    assert result.emotional_effect == ""
    assert result.target_word_count == 0
    assert result.blueprint_id is None
    assert result.volume_arc_id is None


@pytest.mark.asyncio
async def test_chapter_plan_schema_extended_fields(db):
    """ChapterPlanOut 包含新字段并可序列化。"""
    plan = ChapterPlan(
        novel_id=1,
        blueprint_id=2,
        volume_arc_id=3,
        position=1,
        version=3,
        status="ready",
        content_json={"chapter_title": "新章"},
        emotional_effect="温暖感动",
        target_word_count=5000,
        foreshadowing_tasks=[{"type": "reveal", "item": "古剑"}],
        acceptance_criteria="完成感人的告别场景",
    )
    db.add(plan)
    await db.flush()
    out = ChapterPlanOut.model_validate(plan)
    assert out.id == plan.id
    assert out.blueprint_id == 2
    assert out.volume_arc_id == 3
    assert out.version == 3
    assert out.emotional_effect == "温暖感动"
    assert out.target_word_count == 5000
    assert out.foreshadowing_tasks == [{"type": "reveal", "item": "古剑"}]
    assert out.acceptance_criteria == "完成感人的告别场景"


# ── API integration tests ─────────────────────────────────────────────────


async def _register_headers(client, username: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_novel(client, headers: dict[str, str]) -> dict:
    resp = await client.post(
        "/api/v1/novels",
        headers=headers,
        json={"title": "规划测试小说", "description": "用于测试规划模块"},
    )
    assert resp.status_code == 200
    return resp.json()["data"]


async def test_create_volume_arc(client):
    """创建卷弧并验证返回数据。"""
    headers = await _register_headers(client, "arc_user_1")
    novel = await _create_novel(client, headers)
    novel_id = novel["id"]

    payload = {
        "title": "第一卷：崛起",
        "goal": "主角从平凡开始修炼",
        "start_state": "平凡少年",
        "end_state": "初入宗门",
        "order_index": 0,
        "key_events": ["拜师", "觉醒", "试炼"],
        "pacing_notes": "前慢后快",
        "foreshadowing_plan": [{"item": "古剑", "chapter": 3}],
    }
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/planning/volume-arcs",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["novel_id"] == novel_id
    assert data["title"] == "第一卷：崛起"
    assert data["goal"] == "主角从平凡开始修炼"
    assert data["start_state"] == "平凡少年"
    assert data["end_state"] == "初入宗门"
    assert data["order_index"] == 0
    assert data["key_events"] == ["拜师", "觉醒", "试炼"]
    assert data["pacing_notes"] == "前慢后快"
    assert data["status"] == "draft"
    assert "id" in data


async def test_list_volume_arcs_ordered(client):
    """列出卷弧，按 order_index 排序。"""
    headers = await _register_headers(client, "arc_user_2")
    novel = await _create_novel(client, headers)
    novel_id = novel["id"]

    for i, title in enumerate(["卷三", "卷一", "卷二"]):
        await client.post(
            f"/api/v1/novels/{novel_id}/planning/volume-arcs",
            headers=headers,
            json={"title": title, "order_index": i},
        )

    resp = await client.get(
        f"/api/v1/novels/{novel_id}/planning/volume-arcs",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 3
    assert data[0]["order_index"] == 0
    assert data[0]["title"] == "卷三"
    assert data[1]["order_index"] == 1
    assert data[1]["title"] == "卷一"
    assert data[2]["order_index"] == 2
    assert data[2]["title"] == "卷二"


async def test_activate_volume_arc_deactivates_previous(client):
    """激活一个新卷弧，之前激活的卷弧自动变为 archived。"""
    headers = await _register_headers(client, "arc_user_3")
    novel = await _create_novel(client, headers)
    novel_id = novel["id"]

    arc1 = await client.post(
        f"/api/v1/novels/{novel_id}/planning/volume-arcs",
        headers=headers,
        json={"title": "第一卷", "order_index": 0},
    )
    arc1_id = arc1.json()["data"]["id"]
    await client.put(
        f"/api/v1/novels/{novel_id}/planning/volume-arcs/{arc1_id}/activate",
        headers=headers,
    )

    arc2 = await client.post(
        f"/api/v1/novels/{novel_id}/planning/volume-arcs",
        headers=headers,
        json={"title": "第二卷", "order_index": 1},
    )
    arc2_id = arc2.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/planning/volume-arcs/{arc2_id}/activate",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "active"

    get_resp = await client.get(
        f"/api/v1/novels/{novel_id}/planning/volume-arcs/{arc1_id}",
        headers=headers,
    )
    assert get_resp.json()["data"]["status"] == "archived"


async def test_create_plan_version(client):
    """创建计划版本，包含 change_reason 和 impact_scope。"""
    headers = await _register_headers(client, "ver_user_1")
    novel = await _create_novel(client, headers)
    novel_id = novel["id"]

    payload = {
        "plan_type": "volume_arc",
        "plan_id": 1,
        "change_reason": "调整卷弧结构",
        "impact_scope": "第一卷整体走向",
        "snapshot_json": {"title": "第一卷", "goal": "新目标"},
    }
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/planning/plan-versions",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["plan_type"] == "volume_arc"
    assert data["plan_id"] == 1
    assert data["change_reason"] == "调整卷弧结构"
    assert data["impact_scope"] == "第一卷整体走向"
    assert data["snapshot_json"] == {"title": "第一卷", "goal": "新目标"}
    assert data["version"] == 1
    assert data["status"] == "current"


async def test_activate_plan_version(client):
    """激活一个已是 current 的版本应成功（幂等）。"""
    headers = await _register_headers(client, "ver_user_2")
    novel = await _create_novel(client, headers)
    novel_id = novel["id"]

    v1_resp = await client.post(
        f"/api/v1/novels/{novel_id}/planning/plan-versions",
        headers=headers,
        json={"plan_type": "blueprint", "plan_id": 10, "change_reason": "初版", "impact_scope": "全局"},
    )
    v1_id = v1_resp.json()["data"]["id"]

    v2_resp = await client.post(
        f"/api/v1/novels/{novel_id}/planning/plan-versions",
        headers=headers,
        json={"plan_type": "blueprint", "plan_id": 10, "change_reason": "修订版", "impact_scope": "第2章"},
    )
    v2_id = v2_resp.json()["data"]["id"]

    # v2 创建后，v1 应在数据库中被归档
    list_resp = await client.get(
        f"/api/v1/novels/{novel_id}/planning/plan-versions?plan_type=blueprint&plan_id=10",
        headers=headers,
    )
    versions = list_resp.json()["data"]
    v1_from_db = next(v for v in versions if v["id"] == v1_id)
    v2_from_db = next(v for v in versions if v["id"] == v2_id)
    assert v1_from_db["status"] == "archived"
    assert v2_from_db["status"] == "current"

    # 激活已是 current 的 v2（幂等）
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/planning/plan-versions/{v2_id}/activate",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "current"


async def test_archived_plan_version_cannot_activate(client):
    """已归档的版本不能重新激活（400）。"""
    headers = await _register_headers(client, "ver_user_3")
    novel = await _create_novel(client, headers)
    novel_id = novel["id"]

    # 创建版本，然后创建新版本使第一个归档
    v1_resp = await client.post(
        f"/api/v1/novels/{novel_id}/planning/plan-versions",
        headers=headers,
        json={"plan_type": "blueprint", "plan_id": 20, "change_reason": "v1", "impact_scope": "x"},
    )
    v1_id = v1_resp.json()["data"]["id"]

    await client.post(
        f"/api/v1/novels/{novel_id}/planning/plan-versions",
        headers=headers,
        json={"plan_type": "blueprint", "plan_id": 20, "change_reason": "v2", "impact_scope": "x"},
    )

    # 尝试激活已归档的 v1
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/planning/plan-versions/{v1_id}/activate",
        headers=headers,
    )
    assert resp.status_code == 400
    assert "archived" in resp.json()["message"].lower() or "归档" in resp.json()["message"]


async def test_cross_user_404(client):
    """其他用户无法访问或操作卷弧（返回 404）。"""
    headers_a = await _register_headers(client, "cross_a")
    headers_b = await _register_headers(client, "cross_b")
    novel_a = await _create_novel(client, headers_a)
    novel_a_id = novel_a["id"]

    # A 创建一个卷弧
    arc_resp = await client.post(
        f"/api/v1/novels/{novel_a_id}/planning/volume-arcs",
        headers=headers_a,
        json={"title": "A的卷弧", "order_index": 0},
    )
    arc_id = arc_resp.json()["data"]["id"]

    # B 尝试获取该卷弧
    resp = await client.get(
        f"/api/v1/novels/{novel_a_id}/planning/volume-arcs/{arc_id}",
        headers=headers_b,
    )
    assert resp.status_code == 404

    # B 尝试更新该卷弧
    resp = await client.put(
        f"/api/v1/novels/{novel_a_id}/planning/volume-arcs/{arc_id}",
        headers=headers_b,
        json={"title": "B的修改"},
    )
    assert resp.status_code == 404


async def test_planning_dashboard(client):
    """规划仪表盘返回所有关键规划数据。"""
    headers = await _register_headers(client, "dash_user")
    novel = await _create_novel(client, headers)
    novel_id = novel["id"]

    resp = await client.get(
        f"/api/v1/novels/{novel_id}/planning/dashboard",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # 检查结构：active_blueprint, active_volume_arcs, current_chapter_plans,
    # open_review_issues, unresolved_foreshadowings
    assert "active_blueprint" in data
    assert "active_volume_arcs" in data
    assert "current_chapter_plans" in data
    assert "open_review_issues" in data
    assert "unresolved_foreshadowings" in data


# ── ChapterPlan API tests (new for Task 6) ──────────────────────────────────


async def test_chapter_plan_list_get_api(client):
    """GET /chapter-plans 能列出所有章节计划，GET /chapter-plans/{id} 能获取单个。"""
    headers = await _register_headers(client, "cp_user_list")
    novel = await _create_novel(client, headers)
    novel_id = novel["id"]

    # 先创建蓝图并激活
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    bp_id = resp.json()["data"]["id"]
    await client.put(
        f"/api/v1/novels/{novel_id}/blueprints/{bp_id}/activate",
        headers=headers,
    )

    # 生成 2 个章节计划
    resp1 = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-plans/next/generate",
        headers=headers,
    )
    assert resp1.status_code == 200
    plan1 = resp1.json()["data"]
    plan1_id = plan1["id"]

    resp2 = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-plans/next/generate",
        headers=headers,
    )
    assert resp2.status_code == 200

    # 列出所有计划
    list_resp = await client.get(
        f"/api/v1/novels/{novel_id}/chapter-plans",
        headers=headers,
    )
    assert list_resp.status_code == 200
    plans = list_resp.json()["data"]
    assert len(plans) >= 2

    # 获取单个计划
    get_resp = await client.get(
        f"/api/v1/novels/{novel_id}/chapter-plans/{plan1_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["id"] == plan1_id


async def test_chapter_plan_list_active_only(client):
    """GET /chapter-plans?active_only=true 只返回 status=ready 的计划。"""
    headers = await _register_headers(client, "cp_user_active")
    novel = await _create_novel(client, headers)
    novel_id = novel["id"]

    resp = await client.post(
        f"/api/v1/novels/{novel_id}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    bp_id = resp.json()["data"]["id"]
    await client.put(
        f"/api/v1/novels/{novel_id}/blueprints/{bp_id}/activate",
        headers=headers,
    )

    await client.post(
        f"/api/v1/novels/{novel_id}/chapter-plans/next/generate",
        headers=headers,
    )

    list_resp = await client.get(
        f"/api/v1/novels/{novel_id}/chapter-plans?active_only=true",
        headers=headers,
    )
    assert list_resp.status_code == 200
    plans = list_resp.json()["data"]
    assert len(plans) >= 1
    for p in plans:
        assert p["status"] == "ready"


async def test_chapter_plan_update_extended_fields(client):
    """PUT /chapter-plans/{id} 可更新新字段（acceptance_criteria 等）。"""
    headers = await _register_headers(client, "cp_user_upd")
    novel = await _create_novel(client, headers)
    novel_id = novel["id"]

    resp = await client.post(
        f"/api/v1/novels/{novel_id}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    bp_id = resp.json()["data"]["id"]
    await client.put(
        f"/api/v1/novels/{novel_id}/blueprints/{bp_id}/activate",
        headers=headers,
    )

    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-plans/next/generate",
        headers=headers,
    )
    plan_id = resp.json()["data"]["id"]

    update_resp = await client.put(
        f"/api/v1/novels/{novel_id}/chapter-plans/{plan_id}",
        headers=headers,
        json={
            "acceptance_criteria": "需要完成三个场景",
            "target_word_count": 5000,
            "emotional_effect": "悲伤",
        },
    )
    assert update_resp.status_code == 200
    data = update_resp.json()["data"]
    assert data["acceptance_criteria"] == "需要完成三个场景"
    assert data["target_word_count"] == 5000
