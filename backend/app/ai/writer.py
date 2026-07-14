"""AI writing generators: real (DeepSeek) and fake (for testing)."""

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel

from app.ai.agent import create_novel_agent
from app.ai.models import NovelAgentState
from app.ai.plot_planning import (
    AIProtocolError,
    DraftGenerationOutput,
    DraftReviewOutput,
    LocalRevisionOutput,
    PlotPlanOutput,
)
from app.core.config import settings

logger = logging.getLogger("novel_agent.ai.writer")


class BaseWritingGenerator:
    async def generate_blueprint(self, novel_data: dict, author_input: str) -> dict:
        raise NotImplementedError

    async def generate_chapter_plan(self, blueprint: dict, novel_data: dict) -> dict:
        raise NotImplementedError

    async def generate_chapter_brief(self, chapter_plan: dict, blueprint: dict, length_contract: dict) -> dict:
        raise NotImplementedError

    async def generate_draft(self, context_package: dict) -> str:
        raise NotImplementedError

    async def rewrite_fragment(self, draft: str, location: str, context: str, intent: Optional[str] = None) -> str:
        raise NotImplementedError

    async def generate_plot_plan(self, foundation: dict, plot_unit: dict, published_canon: dict) -> dict:
        raise NotImplementedError

    async def generate_draft_result(self, context_package: dict) -> DraftGenerationOutput:
        raise NotImplementedError

    async def review_draft(self, context_package: dict, draft: str) -> DraftReviewOutput:
        raise NotImplementedError

    async def revise_draft(self, context_package: dict, draft: str, conflict: dict, selected_direction: str) -> LocalRevisionOutput:
        raise NotImplementedError


class FakeWritingGenerator(BaseWritingGenerator):
    async def generate_blueprint(self, novel_data: dict, author_input: str) -> dict:
        return {
            "core_promise": "一段英雄与背叛的史诗故事",
            "theme": "权力与责任",
            "main_conflict": "帝国与边疆势力的对抗",
            "character_arcs": "主角从逃避责任到承担使命",
            "world_rules": "五行灵力体系，修炼分为九境",
            "narrative_perspective": "第三人称有限视角",
            "style_constraints": "克制冷调，少用网络化表达",
            "ending_direction": "开放式结局，留续作空间",
        }

    async def generate_chapter_plan(self, blueprint: dict, novel_data: dict) -> dict:
        chapters = novel_data.get("chapters", [])
        return {
            "chapter_title": f"第 {len(chapters) + 1} 章",
            "plot_task": "推进主线冲突",
            "character_task": "展现主角性格变化",
            "information_task": "揭示关键背景信息",
            "emotional_effect": "紧张与期待交织",
            "pacing": "缓起急收，末尾留悬念",
            "foreshadowing_task": "暗示后续重大转折",
        }

    async def generate_chapter_brief(self, chapter_plan: dict, blueprint: dict, length_contract: dict) -> dict:
        return {
            "writing_goal": "完成本章剧情推进，塑造角色形象",
            "scenes": [
                {"name": "场景一 开端", "purpose": "建立本章情绪基调", "conflict": "内部冲突", "expected_words": 800},
                {"name": "场景二 冲突", "purpose": "推进主线矛盾", "conflict": "外部冲突", "expected_words": 1200},
                {"name": "场景三 收束", "purpose": "为下一章埋下伏笔", "conflict": "悬念", "expected_words": 1000},
            ],
            "participating_characters": "主角与反派",
            "conflict_design": "逐步升级的对抗",
            "information_control": "分批揭示",
            "foreshadowing_handling": "含蓄暗示",
            "writing_constraints": "不使用现代词汇",
            "acceptance_criteria": "完成所有剧情任务，字数达标",
        }

    async def generate_draft(self, context_package: dict) -> str:
        paragraph = (
            "边境的风裹挟着沙砾扑面而来，城墙上的旗帜在黄昏中猎猎作响。"
            "主角站在垛口边，目光越过荒原望向远方。"
            "那个方向传来消息已经三天了——没有人知道那意味着什么。"
        )
        return (paragraph + "\n\n") * 20

    async def rewrite_fragment(self, draft: str, location: str, context: str, intent: Optional[str] = None) -> str:
        return draft.replace(location, f"[{location}]", 1)


class FakePhase3WritingGenerator(BaseWritingGenerator):
    def __init__(
        self,
        plot_plan: dict | None = None,
        draft_result: DraftGenerationOutput | None = None,
        review: DraftReviewOutput | None = None,
        revision: LocalRevisionOutput | None = None,
    ):
        self._plot_plan = plot_plan
        self._draft_result = draft_result
        self._review = review
        self._revision = revision

    async def generate_plot_plan(self, foundation: dict, plot_unit: dict, published_canon: dict) -> dict:
        if self._plot_plan is not None:
            return self._plot_plan
        return {
            "starting_state": "当前已发布事实",
            "stage_goal": "完成本阶段目标",
            "core_conflict": "主线冲突",
            "key_turns": [{"order": 1, "event": "关键转折", "required": True}],
            "progression": [{"order": 1, "chapter_position": 1, "purpose": "推进目的", "scenes": ["场景目标"]}],
            "character_changes": [],
            "foreshadowing": [],
            "must_complete": ["必须完成事项"],
            "optional": [],
            "completion_criteria": ["完成判断标准"],
        }

    async def generate_draft_result(self, context_package: dict) -> DraftGenerationOutput:
        if self._draft_result is not None:
            return self._draft_result
        return DraftGenerationOutput(
            status="draft_ready",
            draft="边境的风裹挟着沙砾扑面而来。",
        )

    async def generate_draft(self, context_package: dict) -> str:
        paragraph = (
            "边境的风裹挟着沙砾扑面而来，城墙上的旗帜在黄昏中猎猎作响。"
            "主角站在垛口边，目光越过荒原望向远方。"
            "那个方向传来消息已经三天了——没有人知道那意味着什么。"
        )
        return (paragraph + "\n\n") * 20

    async def review_draft(self, context_package: dict, draft: str) -> DraftReviewOutput:
        if self._review is not None:
            return self._review
        return DraftReviewOutput(
            narrative_conflicts=[],
            quality_issues=[],
            has_continuity_conflicts=False,
            verdict="pass",
        )

    async def revise_draft(self, context_package: dict, draft: str, conflict: dict, selected_direction: str) -> LocalRevisionOutput:
        if self._revision is not None:
            return self._revision
        return LocalRevisionOutput(
            candidate_content=draft,
            scope={"type": "paragraph", "start": 1, "end": 1},
            diff={"old": draft, "new": draft},
            plan_patch={"adjustment": "none"},
            expanded_scope=False,
            expansion_reason="",
        )


class DeepSeekWritingGenerator(BaseWritingGenerator):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.DEEPSEEK_API_KEY

    async def generate_blueprint(self, novel_data: dict, author_input: str) -> dict:
        prompt = f"""根据以下小说信息生成小说蓝图，以 JSON 格式返回。

小说标题：{novel_data.get('title', '')}
小说简介：{novel_data.get('description', '')}
类型：{novel_data.get('genre', '')}
风格指南：{novel_data.get('style_guide', '')}
作者构思：{author_input}

返回 JSON 字段：
- core_promise: 核心卖点
- theme: 主题表达
- main_conflict: 主线冲突
- character_arcs: 主要角色弧光
- world_rules: 世界规则
- narrative_perspective: 叙事视角
- style_constraints: 风格约束
- ending_direction: 结局方向

只返回 JSON，不要其他内容。"""
        return await self._call_llm(prompt)

    async def generate_chapter_plan(self, blueprint: dict, novel_data: dict) -> dict:
        prompt = f"""根据以下小说蓝图和已有章节信息，生成下一章章节大纲，以 JSON 格式返回。

蓝图核心内容：{json.dumps(blueprint, ensure_ascii=False)}
已有章节数：{len(novel_data.get('chapters', []))}

返回 JSON 字段：
- chapter_title: 章节标题
- plot_task: 剧情任务
- character_task: 角色任务
- information_task: 信息任务
- emotional_effect: 情绪效果
- pacing: 节奏目标
- foreshadowing_task: 伏笔任务

只返回 JSON。"""
        return await self._call_llm(prompt)

    async def generate_chapter_brief(self, chapter_plan: dict, blueprint: dict, length_contract: dict) -> dict:
        contract_str = json.dumps(length_contract, ensure_ascii=False)
        prompt = f"""根据以下章节大纲生成章节任务书，以 JSON 格式返回。
篇幅契约：目标{length_contract.get('target_words', 3000)}字，最低{length_contract.get('min_words', 2000)}字。

章节大纲：{json.dumps(chapter_plan, ensure_ascii=False)}

返回 JSON 字段：
- writing_goal: 写作目标
- scenes: 场景拆分数组，每个元素包含 name, purpose, conflict, expected_words
- participating_characters: 出场角色
- conflict_design: 冲突设计
- information_control: 信息控制
- foreshadowing_handling: 伏笔处理
- writing_constraints: 写作约束
- acceptance_criteria: 验收标准

只返回 JSON。"""
        return await self._call_llm(prompt)

    async def generate_draft(self, context_package: dict) -> str:
        brief = context_package.get("chapter_brief", {})
        contract = context_package.get("length_contract", {})
        expansion_hint = context_package.get("expansion_hint", "")
        prompt = f"""请根据以下章节任务书和上下文，写出一章小说正文。

任务书：{json.dumps(brief, ensure_ascii=False)}
字数要求：目标{contract.get('target_words', 3000)}字，最低{contract.get('min_words', 2000)}字

要求：
1. 按章节任务书写正文，不要自由发挥成另一章
2. 按篇幅充分展开场景、冲突、反应、动作、对话和氛围
3. 不输出大纲、列表、总结或解释，只输出章节正文
4. 如果篇幅不足，优先扩写场景过程和角色反应
{('5. ' + expansion_hint) if expansion_hint else ''}"""
        return await self._call_llm_text(prompt)

    async def rewrite_fragment(self, draft: str, location: str, context: str, intent: Optional[str] = None) -> str:
        prompt = f"""请根据以下要求重写小说正文的特定位置。

原正文：
{draft}

需要重写的位置：{location}

上下文信息：
{context}

作者意图：
{intent or '请自行判断最佳方向'}

要求：
1. 只重写指定位置的内容，保持正文其他部分不变
2. 根据作者意图调整该位置的措辞、语气和细节
3. 直接输出完整的新正文，不要任何解释
4. 不要改变正文的整体风格和叙事视角"""
        return await self._call_llm_text(prompt)

    async def generate_plot_plan(self, foundation: dict, plot_unit: dict, published_canon: dict) -> dict:
        prompt = f"""根据以下信息生成剧情规划方案，以 JSON 格式返回。

author_foundation：
{json.dumps(foundation, ensure_ascii=False)}

plot_unit：
{json.dumps(plot_unit, ensure_ascii=False)}

published_canon：
{json.dumps(published_canon, ensure_ascii=False)}

返回 JSON 字段：
- starting_state: 当前已发布事实和人物状态
- stage_goal: 本剧情单元结束时必须达到的状态
- core_conflict: 核心冲突
- key_turns: 关键转折点数组，每项包含 order, event, required
- progression: 推进数组，每项包含 order, chapter_position, purpose, scenes
- character_changes: 角色变化数组，每项包含 character, from, to
- foreshadowing: 伏笔数组，每项包含 action, item, chapter_position
- must_complete: 必须完成事项数组
- optional: 可选事项数组
- completion_criteria: 完成判断标准数组

只返回 JSON。"""
        return await self._call_validated_json(prompt, PlotPlanOutput)

    async def generate_draft_result(self, context_package: dict) -> DraftGenerationOutput:
        plot_plan = context_package.get("plot_plan", {})
        prompt = f"""根据以下剧情规划方案生成正文草稿，以 JSON 格式返回。

剧情规划：
{json.dumps(plot_plan, ensure_ascii=False)}

返回 JSON 字段：
- status: "draft_ready" | "decision_required" | "unsafe_planning"
- draft: 正文草稿
- conflict: 如果遇到冲突，提供冲突对象（可选），包含：
  - source: "during_generation" | "during_review"
  - core_conflict: 核心冲突描述
  - options: 2-3 个不同方案，每项含 label, action, consequence, affected_future_scope
  - recommended_index: 推荐方案索引
  - recommendation_reason: 推荐理由
  - impact_scope: 影响范围
- unsafe_reason: 如果状态为 unsafe_planning，说明原因

当模型认为方案不足 2 个可执行选项时，将 status 设为 unsafe_planning。
只返回 JSON。"""
        return await self._call_validated_json(prompt, DraftGenerationOutput)

    async def review_draft(self, context_package: dict, draft: str) -> DraftReviewOutput:
        plot_plan = context_package.get("plot_plan", {})
        prompt = f"""请审查以下正文草稿是否存在冲突，以 JSON 格式返回。

plot_plan：
{json.dumps(plot_plan, ensure_ascii=False)}

draft：
{draft}

返回 JSON 字段：
- narrative_conflicts: 叙事冲突数组，每项包含 source, core_conflict, options, recommended_index, recommendation_reason, impact_scope
- quality_issues: 质量问题数组，每项包含：
  - issue_type: 问题类型（如 style, character, continuity）
  - severity: 影响程度，"blocking"（阻塞验收）、"major"（重大问题）或 "minor"（轻微问题）
  - resolution_mode: "auto_fixable"（可自动修复）或 "needs_intent"（需要作者意图）
  - location: 问题位置
  - description: 问题描述
  - related_memory: 相关记忆（可选）
  - suggestion: 修复建议
  - acceptance_blocking: 是否阻塞验收（布尔）
- has_continuity_conflicts: 是否有连续性冲突（布尔）
- verdict: "pass" | "revise"

只返回 JSON。"""
        return await self._call_validated_json(prompt, DraftReviewOutput)

    async def revise_draft(self, context_package: dict, draft: str, conflict: dict, selected_direction: str) -> LocalRevisionOutput:
        prompt = f"""根据冲突解决方案修订正文草稿，以 JSON 格式返回。

draft：
{draft}

conflict：
{json.dumps(conflict, ensure_ascii=False)}

selected_direction：{selected_direction}

impact_scope：
{json.dumps(conflict.get("impact_scope", {}), ensure_ascii=False)}

返回 JSON 字段：
- candidate_content: 修订后的正文内容
- scope: 修订范围（如 type, start, end）
- diff: 差异描述（如 old, new）
- plan_patch: 规划补丁
- expanded_scope: 是否扩大了影响范围（布尔）
- expansion_reason: 扩大原因

只返回 JSON。"""
        return await self._call_validated_json(prompt, LocalRevisionOutput)

    async def _call_validated_json(self, prompt: str, model_class: type[BaseModel]) -> Any:
        agent = create_novel_agent(
            model_type="flash",
            tools=[],
            system_prompt="你是一个小说创作辅助AI，只返回JSON格式的输出。",
            state_schema=NovelAgentState,
        )
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}], "novel_id": 0, "chapter_id": 0, "user_id": 0, "pending_confirmations": []},
            {"configurable": {"thread_id": "writer-plot-planning"}},
        )
        content = result["messages"][-1].content if result.get("messages") else ""
        try:
            data = json.loads(content) if content.strip() else {}
        except json.JSONDecodeError as e:
            raise AIProtocolError(f"JSON parse error: {e}") from e
        try:
            if issubclass(model_class, BaseModel) and model_class is not dict:
                return model_class.model_validate(data)
            return data
        except Exception as e:
            raise AIProtocolError(f"Pydantic validation error: {e}") from e

    async def _call_llm(self, prompt: str) -> dict:
        """调用 DeepSeek 返回 JSON。失败时返回空字典。"""
        agent = create_novel_agent(
            model_type="flash",
            tools=[],
            system_prompt="你是一个小说创作辅助AI，只返回JSON格式的输出。",
            state_schema=NovelAgentState,
        )
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}], "novel_id": 0, "chapter_id": 0, "user_id": 0, "pending_confirmations": []},
            {"configurable": {"thread_id": "writer-generate"}},
        )
        content = result["messages"][-1].content if result.get("messages") else "{}"
        try:
            return json.loads(content) if content.strip() else {}
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON response, falling back to empty dict")
            return {}

    async def _call_llm_text(self, prompt: str) -> str:
        agent = create_novel_agent(
            model_type="flash",
            tools=[],
            system_prompt="你是一个小说作者，只输出小说正文，不输出其他内容。",
            state_schema=NovelAgentState,
        )
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}], "novel_id": 0, "chapter_id": 0, "user_id": 0, "pending_confirmations": []},
            {"configurable": {"thread_id": "writer-draft"}},
        )
        return result["messages"][-1].content if result.get("messages") else ""
