"""AI writing generators: real (DeepSeek) and fake (for testing)."""

import json
import logging
from typing import Optional

from app.ai.agent import create_novel_agent
from app.ai.models import NovelAgentState
from app.core.config import settings

logger = logging.getLogger("novel_agent.ai.writer")


class BaseWritingGenerator:
    async def generate_blueprint(self, novel_data: dict, author_input: str) -> dict:
        raise NotImplementedError

    async def generate_chapter_plan(self, blueprint: dict, novel_data: dict) -> dict:
        raise NotImplementedError

    async def generate_chapter_plans_batch(self, blueprint: dict, novel_data: dict, count: int) -> list[dict]:
        raise NotImplementedError

    async def generate_chapter_brief(self, chapter_plan: dict, blueprint: dict, length_contract: dict) -> dict:
        raise NotImplementedError

    async def generate_draft(self, context_package: dict) -> str:
        raise NotImplementedError

    async def rewrite_fragment(self, draft: str, location: str, context: str, intent: Optional[str] = None) -> str:
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

    async def generate_chapter_plans_batch(self, blueprint: dict, novel_data: dict, count: int) -> list[dict]:
        chapters = novel_data.get("chapters", [])
        base = len(chapters) + 1
        return [
            {
                "chapter_title": f"第 {base + i} 章",
                "plot_task": f"推进主线冲突（批次 {i+1}）",
                "character_task": "展现主角性格变化",
                "information_task": "揭示关键背景信息",
                "emotional_effect": "紧张与期待交织",
                "pacing": "缓起急收，末尾留悬念",
                "foreshadowing_task": "暗示后续重大转折",
            }
            for i in range(count)
        ]

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

    async def generate_chapter_plans_batch(self, blueprint: dict, novel_data: dict, count: int) -> list[dict]:
        prompt = f"""根据以下小说蓝图和已有章节信息，生成 {count} 章连续的章节大纲，以 JSON 数组格式返回。

蓝图核心内容：{json.dumps(blueprint, ensure_ascii=False)}
已有章节数：{len(novel_data.get('chapters', []))}

每章返回 JSON 字段：
- chapter_title: 章节标题
- plot_task: 剧情任务
- character_task: 角色任务
- information_task: 信息任务
- emotional_effect: 情绪效果
- pacing: 节奏目标
- foreshadowing_task: 伏笔任务

只返回 JSON 数组。"""
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
