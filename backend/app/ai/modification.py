"""Phase 4 修改代理——结构化修复选项生成与局部修订。

包含:
- Pydantic 输出模型: RepairOption, RepairOptionsOutput, RevisionPatch, ModificationOutput
- BaseModificationAgent: 抽象基类
- FakeModificationAgent: 测试用确定性假代理
- DeepSeekModificationAgent: DeepSeek 结构化输出实现
"""

import abc
import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.ai.plot_planning import AIProtocolError
from app.ai.writer import DeepSeekWritingGenerator

logger = logging.getLogger("novel_agent.ai.modification")


# ── Pydantic protocol models ──────────────────────────────────────────


class RepairOption(BaseModel):
    """单个修复选项。"""

    label: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    action: str = Field(min_length=1)
    expected_effect: str = Field(min_length=1)
    estimated_scope: dict
    recommended: bool = False
    recommendation_reason: str = ""


class RepairOptionsOutput(BaseModel):
    """修复选项列表输出。"""

    options: list[RepairOption] = Field(min_length=1, max_length=3)
    single_option_reason: str | None = None

    @model_validator(mode="after")
    def validate_options(self) -> "RepairOptionsOutput":
        # 拒绝重复的 action
        actions = [opt.action for opt in self.options]
        if len(actions) != len(set(actions)):
            raise ValueError("修复选项的 action 不能重复")

        # 拒绝多个 recommended
        recommended_count = sum(1 for opt in self.options if opt.recommended)
        if recommended_count > 1:
            raise ValueError("最多只能有一个推荐选项")

        # 只有一个选项时必须有 single_option_reason
        if len(self.options) == 1 and not self.single_option_reason:
            raise ValueError("只有一个选项时必须提供 single_option_reason")

        return self


class RevisionPatch(BaseModel):
    """单个修订补丁。"""

    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    original_text: str
    replacement_text: str
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_offsets(self) -> "RevisionPatch":
        if self.end_offset < self.start_offset:
            raise ValueError("end_offset 不能小于 start_offset")
        return self


class ModificationOutput(BaseModel):
    """修改输出，包含候选内容、补丁列表和范围信息。"""

    candidate_content: str
    patches: list[RevisionPatch] = Field(min_length=1)
    diff: dict
    change_reason: str = Field(min_length=1)
    scope: dict
    expanded_scope: bool = False
    expanded_scope_reason: str | None = None

    @model_validator(mode="after")
    def validate_patches_and_scope(self) -> "ModificationOutput":
        # 拒绝反转/重叠的 patch offsets
        offsets = [(p.start_offset, p.end_offset) for p in self.patches]
        sorted_offsets = sorted(offsets, key=lambda x: x[0])
        for i in range(1, len(sorted_offsets)):
            if sorted_offsets[i][0] < sorted_offsets[i - 1][1]:
                raise ValueError("补丁偏移量重叠或反转")

        # expanded_scope=true 时必须有 reason
        if self.expanded_scope and not self.expanded_scope_reason:
            raise ValueError("扩大范围时必须提供 expanded_scope_reason")

        return self


# ── Agent base class ──────────────────────────────────────────────────


class BaseModificationAgent(abc.ABC):
    """修改代理抽象基类。"""

    @abc.abstractmethod
    async def generate_options(self, context: dict) -> RepairOptionsOutput:
        """根据上下文生成修复选项。"""
        ...

    @abc.abstractmethod
    async def create_revision(self, context: dict) -> ModificationOutput:
        """根据上下文生成修改修订。"""
        ...


# ── Fake agent for testing ────────────────────────────────────────────


class FakeModificationAgent(BaseModificationAgent):
    """确定性假代理，用于测试。"""

    def __init__(
        self,
        options_output: RepairOptionsOutput | None = None,
        modification_output: ModificationOutput | None = None,
        generate_options_error: Exception | None = None,
        create_revision_error: Exception | None = None,
    ):
        self._options_output = options_output
        self._modification_output = modification_output
        self._generate_options_error = generate_options_error
        self._create_revision_error = create_revision_error

    async def generate_options(self, context: dict) -> RepairOptionsOutput:
        if self._generate_options_error:
            raise self._generate_options_error
        if self._options_output is not None:
            return self._options_output
        # Default: return a single option
        return RepairOptionsOutput(
            options=[
                RepairOption(
                    label="修改措辞",
                    summary="修改问题段落的措辞",
                    action="replace_text",
                    expected_effect="消除连续性问题",
                    estimated_scope={"type": "paragraph", "chars": 50},
                    recommended=True,
                    recommendation_reason="最小影响范围",
                )
            ],
            single_option_reason="问题明确，只需一种修法",
        )

    async def create_revision(self, context: dict) -> ModificationOutput:
        if self._create_revision_error:
            raise self._create_revision_error
        if self._modification_output is not None:
            return self._modification_output
        # Default: return a simple patch
        base = context.get("current_content", "")
        if base:
            patch = RevisionPatch(
                start_offset=0,
                end_offset=min(len(base), 10),
                original_text=base[: min(len(base), 10)],
                replacement_text=base[: min(len(base), 10)],
                reason="默认无变化补丁",
            )
            return ModificationOutput(
                candidate_content=base,
                patches=[patch],
                diff={"old": base, "new": base},
                change_reason="测试修改",
                scope={"type": "paragraph", "chars": 10},
            )
        return ModificationOutput(
            candidate_content="",
            patches=[
                RevisionPatch(
                    start_offset=0,
                    end_offset=0,
                    original_text="",
                    replacement_text="",
                    reason="空内容补丁",
                )
            ],
            diff={},
            change_reason="测试修改",
            scope={"type": "paragraph"},
        )


# ── DeepSeek implementation ──────────────────────────────────────────


class DeepSeekModificationAgent(BaseModificationAgent):
    """DeepSeek 结构化输出修改代理。"""

    def __init__(self, api_key: str | None = None):
        self._writer = DeepSeekWritingGenerator(api_key=api_key)

    async def generate_options(self, context: dict) -> RepairOptionsOutput:
        prompt = self._build_options_prompt(context)
        return await self._writer._call_validated_json(prompt, RepairOptionsOutput)

    async def create_revision(self, context: dict) -> ModificationOutput:
        prompt = self._build_revision_prompt(context)
        return await self._writer._call_validated_json(prompt, ModificationOutput)

    # ── Prompt builders ────────────────────────────────────────────

    def _build_options_prompt(self, context: dict) -> str:
        current_content = context.get("current_content", "")
        issue = context.get("issue", {})
        chapter_brief = context.get("chapter_brief", {})
        context_snapshot = context.get("context_snapshot", {})
        author_foundation = context.get("author_foundation", {})
        plot_plan = context.get("plot_plan", {})
        published_facts = context.get("published_facts", [])

        return f"""你是一名小说审稿修改助手，根据审阅问题生成修复选项。

当前正文：
{current_content}

审阅问题：
- 类型：{issue.get('issue_type', '')}
- 严重度：{issue.get('severity', '')}
- 位置：{issue.get('location', '')}
- 描述：{issue.get('description', '')}
- 相关记忆：{issue.get('related_memory', '')}
- 建议：{issue.get('suggestion', '')}

章节任务书：{json.dumps(chapter_brief, ensure_ascii=False)}
上下文快照：{json.dumps(context_snapshot, ensure_ascii=False)}
作者基础：{json.dumps(author_foundation, ensure_ascii=False)}
当前剧情规划：{json.dumps(plot_plan, ensure_ascii=False)}
已发布事实：{json.dumps(published_facts, ensure_ascii=False)}

要求：
1. 提供 1-3 个不同的修复选项，每个选项的 action 不能重复
2. 每个选项必须包含 label、summary、action、expected_effect、estimated_scope
3. 最多标记一个选项为 recommended 并提供 recommendation_reason
4. 如果只有一个选项，必须提供 single_option_reason 说明原因
5. 所有修复不得改变与问题无关的文本

返回 JSON 格式：
{{
  "options": [
    {{
      "label": "选项标签",
      "summary": "选项摘要",
      "action": "操作类型",
      "expected_effect": "预期效果",
      "estimated_scope": {{"type": "...", "chars": 0}},
      "recommended": false,
      "recommendation_reason": ""
    }}
  ],
  "single_option_reason": null
}}

只返回 JSON，不要其他内容。"""

    def _build_revision_prompt(self, context: dict) -> str:
        current_content = context.get("current_content", "")
        issue = context.get("issue", {})
        selected_option = context.get("selected_option", {})
        custom_intent = context.get("custom_intent", "")
        chapter_brief = context.get("chapter_brief", {})
        context_snapshot = context.get("context_snapshot", {})
        author_foundation = context.get("author_foundation", {})
        plot_plan = context.get("plot_plan", {})
        published_facts = context.get("published_facts", [])

        intent_section = ""
        if custom_intent:
            intent_section = f"作者自定义意图：{custom_intent}"
        elif selected_option:
            intent_section = f"选中的修复选项：{json.dumps(selected_option, ensure_ascii=False)}"

        return f"""你是一名小说审稿修改助手，根据选定的修复方案生成局部修订。

当前正文：
{current_content}

审阅问题：
- 类型：{issue.get('issue_type', '')}
- 严重度：{issue.get('severity', '')}
- 位置：{issue.get('location', '')}
- 描述：{issue.get('description', '')}
- 相关记忆：{issue.get('related_memory', '')}
- 建议：{issue.get('suggestion', '')}

{intent_section}

章节任务书：{json.dumps(chapter_brief, ensure_ascii=False)}
上下文快照：{json.dumps(context_snapshot, ensure_ascii=False)}
作者基础：{json.dumps(author_foundation, ensure_ascii=False)}
当前剧情规划：{json.dumps(plot_plan, ensure_ascii=False)}
已发布事实：{json.dumps(published_facts, ensure_ascii=False)}

要求：
1. 生成修订后的完整正文（candidate_content）
2. 提供 patches 数组，每个 patch 包含 start_offset、end_offset、original_text、replacement_text、reason
3. start_offset 和 end_offset 是基于当前正文的字符偏移量
4. original_text 必须与当前正文中对应位置的文本完全一致
5. 与问题无关的文本必须逐字不变
6. 如果修改范围超出问题位置的 300 字上下文窗口，必须设置 expanded_scope=true 并提供 expanded_scope_reason
7. 偏移量不能反转或重叠

返回 JSON 格式：
{{
  "candidate_content": "修订后的完整正文",
  "patches": [
    {{
      "start_offset": 0,
      "end_offset": 0,
      "original_text": "原文片段",
      "replacement_text": "替换文本",
      "reason": "修改原因"
    }}
  ],
  "diff": {{"summary": "变更摘要"}},
  "change_reason": "整体变更原因",
  "scope": {{"type": "...", "chars": 0}},
  "expanded_scope": false,
  "expanded_scope_reason": null
}}

只返回 JSON，不要其他内容。"""
