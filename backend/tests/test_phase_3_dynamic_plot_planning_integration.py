"""Real DeepSeek integration tests for Phase 3 (dynamic plot planning).

Skipped when DEEPSEEK_API_KEY is not configured.
"""

import os

import pytest

from app.ai.writer import DeepSeekWritingGenerator, FakePhase3WritingGenerator

pytestmark = pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not configured",
)


async def _create_locked_chapter(client, novel_id, headers, content="发布事实"):
    response = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        headers=headers,
        json={"title": "已发布章", "content": content, "status": "draft"},
    )
    chapter = response.json()["data"]
    from app.core.database import async_session_factory
    from app.repositories.novel_repo import ChapterRepo
    async with async_session_factory() as session:
        repo = ChapterRepo(session)
        ch = await repo.get_by_id(chapter["id"])
        await repo.update(ch, title=None, content=None, summary=None, status="locked")
    response = await client.get(f"/api/v1/novels/{novel_id}/chapters/{chapter['id']}", headers=headers)
    return response.json()["data"]


@pytest.mark.asyncio
async def test_real_context_includes_author_foundation_and_locked_chapters(client, db):
    from app.services.context_package_service import ContextPackageService
    from app.models.writing import ChapterPlan, ChapterBrief

    response = await client.post("/api/v1/auth/register", json={"username": "int_user1", "password": "password123"})
    token = response.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post("/api/v1/novels", headers=headers, json={"title": "集成测试", "genre": "推理"})
    novel = response.json()["data"]
    novel_id = novel["id"]

    resp = await client.put(
        f"/api/v1/novels/{novel_id}/author-foundation",
        headers=headers,
        json={
            "outline": "边城少年调查旧案真相",
            "current_intent": "推进主线",
            "stage_goal": "找到关键证人",
            "constraints_json": {"tone": "克制", "must_keep": ["旧案线索"]},
        },
    )
    assert resp.status_code == 200

    locked = await _create_locked_chapter(client, novel_id, headers, "边城牢狱中关押着一名神秘囚犯")

    cp = ChapterPlan(novel_id=novel_id, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(cp)
    await db.flush()
    brief = ChapterBrief(
        novel_id=novel_id, chapter_plan_id=cp.id,
        brief_json={"writing_goal": "揭示囚犯身份"},
        length_contract_json={"target_words": 10, "min_words": 1, "max_words": 100},
        status="ready",
    )
    db.add(brief)
    await db.commit()

    from app.repositories.plot_planning_repo import PlotPlanningRepo
    from app.models.plot_planning import PlotUnit, PlotPlanRevision

    pp_repo = PlotPlanningRepo(db)
    revision = await pp_repo.get_latest_foundation_revision(novel_id)
    unit = PlotUnit(
        novel_id=novel_id, title="单元", scope_type="volume",
        start_position=1, end_position=5, foundation_revision_id=revision.id,
    )
    db.add(unit)
    await db.flush()
    plan = PlotPlanRevision(
        novel_id=novel_id, plot_unit_id=unit.id, foundation_revision_id=revision.id,
        version=1, plan_json={"core_conflict": "调查受阻"}, status="active",
    )
    db.add(plan)
    await db.commit()

    ctx = await ContextPackageService(db, user_id=1, novel_id=novel_id).build_for_brief(
        brief_id=brief.id,
        plot_plan_revision_id=plan.id,
        author_input="囚犯可能是关键",
    )

    assert "author_foundation" in ctx
    assert ctx["author_foundation"].get("outline") == "边城少年调查旧案真相"
    assert locked["id"] in ctx["snapshot"]["published_chapter_ids"]
    assert ctx["snapshot"]["plot_plan_revision_id"] == plan.id
    fake_default_ctx = await FakePhase3WritingGenerator().generate_plot_plan(
        {"outline": ""}, {"title": ""}, {"chapters": []},
    )
    assert ctx["plot_plan"] != fake_default_ctx


@pytest.mark.asyncio
async def test_real_planning_differs_from_fake():
    generator = DeepSeekWritingGenerator()
    foundation = {
        "outline": "少年调查边城旧案",
        "current_intent": "推进主线",
        "stage_goal": "找到真相",
        "constraints_json": {},
    }
    plot_unit = {
        "title": "第一卷", "scope_type": "volume",
        "start_position": 1, "end_position": 5,
        "author_goal": "查清旧案", "start_state": "主角抵达边城", "end_state": "真相浮现",
    }
    published_canon = {"chapters": [{"id": 1, "title": "序章", "content": "囚犯被关押", "summary": ""}]}
    fake_default = await FakePhase3WritingGenerator().generate_plot_plan(foundation, plot_unit, published_canon)

    from app.ai.plot_planning import PlotPlanOutput, AIProtocolError
    try:
        result = await generator.generate_plot_plan(foundation, plot_unit, published_canon)
        assert isinstance(result, (dict, PlotPlanOutput))
        assert result != fake_default
        assert result.core_conflict is not None
        assert result.progression is not None
        assert len(result.progression) >= 1
    except AIProtocolError as e:
        error_str = str(e)
        assert "边城" in error_str or "旧案" in error_str or "调查" in error_str


@pytest.mark.asyncio
async def test_real_draft_result_contains_structured_fields(client, db):
    from app.services.context_package_service import ContextPackageService
    from app.models.writing import ChapterPlan, ChapterBrief

    response = await client.post("/api/v1/auth/register", json={"username": "int_user2", "password": "password123"})
    token = response.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post("/api/v1/novels", headers=headers, json={"title": "集成测试2", "genre": "推理"})
    novel = response.json()["data"]
    novel_id = novel["id"]

    resp = await client.put(
        f"/api/v1/novels/{novel_id}/author-foundation",
        headers=headers,
        json={"outline": "大纲", "current_intent": "意图", "stage_goal": "目标", "constraints_json": {}},
    )
    assert resp.status_code == 200

    cp = ChapterPlan(novel_id=novel_id, position=1, content_json={"chapter_title": "第一章"}, status="ready")
    db.add(cp)
    await db.flush()
    brief = ChapterBrief(
        novel_id=novel_id, chapter_plan_id=cp.id,
        brief_json={"writing_goal": "测试生成"},
        length_contract_json={"target_words": 10, "min_words": 1, "max_words": 100},
        status="ready",
    )
    db.add(brief)
    await db.commit()

    from app.repositories.plot_planning_repo import PlotPlanningRepo
    from app.models.plot_planning import PlotUnit, PlotPlanRevision

    pp_repo = PlotPlanningRepo(db)
    revision = await pp_repo.get_latest_foundation_revision(novel_id)
    unit = PlotUnit(
        novel_id=novel_id, title="单元", scope_type="volume",
        start_position=1, end_position=5, foundation_revision_id=revision.id,
    )
    db.add(unit)
    await db.flush()
    plan = PlotPlanRevision(
        novel_id=novel_id, plot_unit_id=unit.id, foundation_revision_id=revision.id,
        version=1, plan_json={"core_conflict": "冲突"}, status="active",
    )
    db.add(plan)
    await db.commit()

    ctx = await ContextPackageService(db, user_id=1, novel_id=novel_id).build_for_brief(
        brief_id=brief.id, plot_plan_revision_id=plan.id,
    )

    from app.ai.plot_planning import AIProtocolError
    generator = DeepSeekWritingGenerator()
    try:
        result = await generator.generate_draft_result(ctx)
        assert result.status in ("draft_ready", "decision_required", "unsafe_planning")
        if result.status == "draft_ready":
            assert result.draft != ""
        elif result.status == "decision_required":
            assert result.conflict is not None
            assert result.conflict.core_conflict
            assert len(result.conflict.options) >= 2
            assert result.conflict.recommended_index is not None
        elif result.status == "unsafe_planning":
            assert result.unsafe_reason is not None
        fake_default = await FakePhase3WritingGenerator().generate_draft_result(ctx)
        assert result.draft != fake_default.draft or result.status != fake_default.status
    except AIProtocolError as e:
        error_str = str(e)
        assert "draft_ready" in error_str or "decision" in error_str.lower() or "规划" in error_str
