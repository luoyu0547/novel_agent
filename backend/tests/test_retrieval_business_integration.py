import json

import pytest

from app.ai.writer import DeepSeekWritingGenerator
from app.core.config import settings
from app.models.foreshadowing import Foreshadowing
from app.models.plot_fact import PlotFact
from app.models.user import User
from app.models.novel import Chapter, Novel
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.api import writing as writing_api


def test_writing_api_injects_production_retrieval_provider(monkeypatch):
    sentinel = object()
    captured = {}

    class CapturingWritingService:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(writing_api, "WritingService", CapturingWritingService)
    monkeypatch.setattr(writing_api, "get_retrieval_provider", lambda: sentinel)

    writing_api._get_service(object(), User(id=1), 7)

    assert captured["retrieval"] is sentinel


@pytest.mark.asyncio
async def test_writer_prompt_contains_writer_context_and_guard(monkeypatch):
    generator = DeepSeekWritingGenerator()
    captured = {}

    async def fake_call(prompt):
        captured["prompt"] = prompt
        return "正文"

    monkeypatch.setattr(generator, "_call_llm_text", fake_call)

    await generator.generate_draft({
        "chapter_brief": {"writing_goal": "调查账册"},
        "length_contract": {"target_words": 1000},
        "retrieved_context": [{"source_id": "chapter:1:scene:0", "text": "账册藏在西厢"}],
        "risk_guard": [{"constraint": "本章不得确认账册去向"}],
    })

    assert "账册藏在西厢" in captured["prompt"]
    assert "本章不得确认账册去向" in captured["prompt"]


@pytest.mark.asyncio
async def test_structured_writer_prompt_contains_retrieval_context(monkeypatch):
    generator = DeepSeekWritingGenerator()
    captured = {}

    async def fake_call(prompt, model_class):
        captured["prompt"] = prompt
        return {"status": "draft_ready", "draft": "正文"}

    monkeypatch.setattr(generator, "_call_validated_json", fake_call)

    await generator.generate_draft_result({
        "plot_plan": {"core_conflict": "调查"},
        "chapter_brief": {"writing_goal": "完成调查"},
        "retrieved_context": [{"text": "旧案发生在北境"}],
        "risk_guard": [{"constraint": "不得提前揭示凶手"}],
    })

    assert "旧案发生在北境" in captured["prompt"]
    assert "不得提前揭示凶手" in captured["prompt"]


def test_quality_prompt_excludes_snapshot_diagnostics():
    from app.ai.quality_agents import TaskCompletionChecker

    prompt = TaskCompletionChecker()._build_prompt(
        "正文",
        {"writing_goal": "调查"},
        {
            "retrieved_context": [{"text": "可用事实"}],
            "risk_guard": [{"constraint": "不得剧透"}],
            "snapshot": {"diagnostics": {"secret_score": 0.99}},
        },
    )

    assert "可用事实" in prompt
    assert "不得剧透" in prompt
    assert "secret_score" not in prompt


def test_context_package_api_projection_hides_retrieval_mechanics():
    public = writing_api._public_context_package_json({
        "characters": [{"name": "沈砚"}],
        "retrieved_context": [{"text": "内部正文"}],
        "risk_guard": [{"constraint": "内部约束"}],
        "snapshot": {
            "source_items": [{"source_id": "chapter:1:scene:0"}],
            "diagnostics": {"writer_candidates": ["secret"]},
        },
    })

    assert public == {"characters": [{"name": "沈砚"}]}


@pytest.mark.asyncio
async def test_legacy_context_loads_facts_and_safe_foreshadowing(db):
    user = User(username="legacy-context", hashed_password="hash")
    db.add(user)
    await db.flush()
    novel = Novel(user_id=user.id, title="长篇")
    db.add(novel)
    await db.flush()
    chapter = Chapter(novel_id=novel.id, title="第一章", content="", summary="", status="locked")
    db.add(chapter)
    await db.flush()
    db.add(PlotFact(
        novel_id=novel.id,
        chapter_id=chapter.id,
        fact_type="event",
        content="军饷失踪",
        importance="major",
    ))
    db.add(Foreshadowing(
        novel_id=novel.id,
        planted_chapter_id=chapter.id,
        name="旧玉佩",
        description="主角随身携带的玉佩",
        hidden_truth="玉佩来自皇室密库",
        status="planted",
        risk_warning="不得提前揭示来源",
    ))
    await db.commit()

    from app.services.writing_service import WritingService
    from app.models.writing import ChapterBrief

    brief = ChapterBrief(
        novel_id=novel.id,
        chapter_plan_id=1,
        brief_json={},
        length_contract_json={},
        status="ready",
    )
    db.add(brief)
    await db.commit()

    loaded_novel = (await db.execute(
        select(Novel)
        .where(Novel.id == novel.id)
        .options(
            selectinload(Novel.chapters),
            selectinload(Novel.characters),
            selectinload(Novel.world_settings),
        )
    )).scalar_one()
    package = await WritingService(db, user.id, novel.id)._build_context_package(loaded_novel, brief)

    assert package["plot_facts"][0]["content"] == "军饷失踪"
    assert package["foreshadowings"][0]["name"] == "旧玉佩"
    assert "hidden_truth" not in json.dumps(package["foreshadowings"], ensure_ascii=False)
    assert "risk_warning" not in json.dumps(package["foreshadowings"], ensure_ascii=False)


def test_runtime_factory_respects_retrieval_switch(monkeypatch):
    from app.retrieval.runtime import get_retrieval_provider

    get_retrieval_provider.cache_clear()
    monkeypatch.setattr(settings, "RETRIEVAL_ENABLED", False)
    assert get_retrieval_provider() is None
    get_retrieval_provider.cache_clear()


def test_extraction_context_has_a_bounded_memory_section():
    from app.ai.tools.context import _bounded_section

    context = _bounded_section("[已有设定]", ["设定内容" * 2000])

    assert len(context) < 5200
    assert "其余内容已省略" in context


@pytest.mark.asyncio
async def test_retrieval_uses_target_chapter_for_proximity_boost():
    from app.retrieval.contracts import HybridEmbedding, RetrievedSource, RerankResult, RetrievalRequest
    from app.retrieval.service import RetrievalService

    class Embedder:
        async def embed_query(self, query):
            return HybridEmbedding([0.1], [1], [1.0])

    class Reranker:
        async def rerank(self, query, documents):
            return [RerankResult(index=0, score=1.0), RerankResult(index=1, score=0.9)]

    class Store:
        async def hybrid_search(self, **kwargs):
            visibility = kwargs["visibility"]
            if visibility == "guard":
                return []
            return [
                RetrievedSource("chapter:1", "chapter_scene", "旧章", "旧", {}, chapter_id=1),
                RetrievedSource("chapter:2", "chapter_scene", "当前章", "当前", {}, chapter_id=2),
            ]

    result = await RetrievalService(
        embedder=Embedder(),
        reranker=Reranker(),
        store=Store(),
    ).retrieve(RetrievalRequest(user_id=1, novel_id=1, query="当前", target_chapter_id=2))

    assert [item["source_id"] for item in result.writer_items] == ["chapter:2", "chapter:1"]


@pytest.mark.asyncio
async def test_context_package_uses_recent_summaries_instead_of_full_locked_content(db):
    from app.models.novel import Chapter
    from app.models.writing import ChapterBrief
    from app.services.context_package_service import ContextPackageService

    user = User(username="summary-only", hashed_password="hash")
    db.add(user)
    await db.flush()
    novel = Novel(user_id=user.id, title="长篇")
    db.add(novel)
    await db.flush()
    db.add(Chapter(
        novel_id=novel.id,
        title="第一章",
        content="整章正文不应进入上下文包" * 100,
        summary="第一章摘要",
        status="locked",
    ))
    await db.flush()
    brief = ChapterBrief(
        novel_id=novel.id,
        chapter_plan_id=1,
        brief_json={},
        length_contract_json={},
        status="ready",
    )
    db.add(brief)
    await db.commit()

    service = ContextPackageService(db, user.id, novel.id)
    # This path requires a plot revision, so assert the baseline helper's public shape
    # through the legacy package builder used by Phase 1/2.
    from app.services.writing_service import WritingService
    loaded_novel = (await db.execute(
        select(Novel)
        .where(Novel.id == novel.id)
        .options(
            selectinload(Novel.chapters),
            selectinload(Novel.characters),
            selectinload(Novel.world_settings),
        )
    )).scalar_one()
    package = await WritingService(db, user.id, novel.id)._build_context_package(loaded_novel, brief)

    assert "整章正文不应进入上下文包" not in json.dumps(package, ensure_ascii=False)
