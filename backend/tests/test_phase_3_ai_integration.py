"""Phase 3 AI integration tests: prompt assertion with monkeypatch."""

import pytest

from app.ai.writer import DeepSeekWritingGenerator


@pytest.mark.asyncio
async def test_generate_plot_plan_prompt_contains_keywords():
    async def fake_call_validated_json(prompt, model_type):
        assert "author_foundation" in prompt
        assert "published_canon" in prompt
        return {}

    gen = DeepSeekWritingGenerator(api_key="test-key")
    gen._call_validated_json = fake_call_validated_json

    result = await gen.generate_plot_plan(
        foundation={"outline": "test"},
        plot_unit={"title": "unit"},
        published_canon={"chapters": []},
    )
    assert result == {}


@pytest.mark.asyncio
async def test_review_draft_prompt_contains_keywords():
    async def fake_call_validated_json(prompt, model_type):
        assert "draft" in prompt
        assert "plot_plan" in prompt
        return {"verdict": "pass", "narrative_conflicts": [], "quality_issues": [], "has_continuity_conflicts": False}

    gen = DeepSeekWritingGenerator(api_key="test-key")
    gen._call_validated_json = fake_call_validated_json

    result = await gen.review_draft(
        context_package={"plot_plan": {}, "chapter_brief": {}},
        draft="some draft content",
    )
    assert result["verdict"] == "pass"


@pytest.mark.asyncio
async def test_revise_draft_prompt_contains_keywords():
    async def fake_call_validated_json(prompt, model_type):
        assert "draft" in prompt
        assert "impact_scope" in prompt
        return {
            "candidate_content": "revised",
            "scope": {"type": "paragraph", "start": 1, "end": 1},
            "diff": {"old": "text", "new": "revised"},
            "plan_patch": {"adjustment": "tone"},
            "expanded_scope": False,
            "expansion_reason": "",
        }

    gen = DeepSeekWritingGenerator(api_key="test-key")
    gen._call_validated_json = fake_call_validated_json

    result = await gen.revise_draft(
        context_package={"plot_plan": {}},
        draft="some draft content",
        conflict={"core_conflict": "test conflict"},
        selected_direction="adjust_goal",
    )
    assert result["candidate_content"] == "revised"
