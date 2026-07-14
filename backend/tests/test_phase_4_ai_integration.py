"""Phase 4 AI integration tests for the Modification Agent.

Tests real DeepSeek output parsing. Marked with pytest.mark.integration
and key-based skipif. Skipped when DEEPSEEK_API_KEY is not configured.
"""

import os

import pytest

from app.ai.modification import (
    DeepSeekModificationAgent,
    ModificationOutput,
    RepairOptionsOutput,
)
from app.services.modification_service import apply_patches


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not configured",
)
@pytest.mark.asyncio
async def test_generate_options_real_output():
    """Real DeepSeek call: output parses as RepairOptionsOutput with 1-3 distinct options."""
    agent = DeepSeekModificationAgent()

    context = {
        "current_content": "他走进房间，看到桌上放着一封信。他拿起信，拆开信封。",
        "issue": {
            "issue_type": "style",
            "severity": "auto_fixable",
            "location": "他走进房间",
            "description": "连续使用'他'开头，造成句式单调",
            "related_memory": "",
            "suggestion": "变换句式主语或合并句子",
        },
        "chapter_brief": {"writing_goal": "推进剧情"},
        "context_snapshot": {},
        "author_foundation": {},
        "plot_plan": {},
        "published_facts": [],
    }

    output = await agent.generate_options(context)
    assert isinstance(output, RepairOptionsOutput)
    assert 1 <= len(output.options) <= 3

    # Distinct actions
    actions = [opt.action for opt in output.options]
    assert len(actions) == len(set(actions))

    # If only one option, single_option_reason must be present
    if len(output.options) == 1:
        assert output.single_option_reason is not None


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not configured",
)
@pytest.mark.asyncio
async def test_create_revision_reconstructs_from_patches():
    """Real DeepSeek call: candidate_content equals patch reconstruction."""
    agent = DeepSeekModificationAgent()

    base_content = "他走进房间，看到桌上放着一封信。他拿起信，拆开信封。信纸上写着几行字，墨迹已经褪色。"
    context = {
        "current_content": base_content,
        "issue": {
            "issue_type": "style",
            "severity": "auto_fixable",
            "location": "他走进房间",
            "description": "连续使用'他'开头，造成句式单调",
            "related_memory": "",
            "suggestion": "变换句式主语或合并句子",
        },
        "selected_option": {
            "label": "合并句子",
            "action": "merge_sentences",
            "summary": "合并前两句以消除重复主语",
        },
        "chapter_brief": {"writing_goal": "推进剧情"},
        "context_snapshot": {},
        "author_foundation": {},
        "plot_plan": {},
        "published_facts": [],
    }

    output = await agent.create_revision(context)
    assert isinstance(output, ModificationOutput)
    assert len(output.patches) >= 1

    # Reconstruct candidate from patches
    reconstructed = apply_patches(base_content, output.patches)
    assert reconstructed == output.candidate_content
