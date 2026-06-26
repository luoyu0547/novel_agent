import logging

from langgraph.checkpoint.memory import InMemorySaver

from app.ai.agent import create_novel_agent, create_novel_deep_agent
from app.ai.models import NovelAgentState
from app.ai.middleware.logging import logging_middleware
from app.ai.tools.context import get_chapter_context
from app.ai.tools.memory import (
    save_character_changes,
    save_plot_facts,
    save_world_settings,
    save_foreshadowing_candidates,
)
from app.repositories.pending_memory_repo import PendingMemoryRepo
from app.core.database import async_session_factory

logger = logging.getLogger("novel_agent.ai")

STANDARD_PROMPT = """你是一个小说创作辅助 Agent，负责分析章节内容并提取结构化信息。

## 工作流程
1. 使用 get_chapter_context 工具获取章节内容和相关记忆
2. 分析内容，提取以下信息：
   - 角色变化（性格、动机、状态、关系的变化）
   - 剧情事实（本章发生的重要事件）
   - 世界观设定（新出现的地点、组织、规则）
   - 伏笔候选（看似普通但可能重要的信息）
3. 使用对应的 save_* 工具写入提取结果

## 规则
- 只提取本章有明确依据的信息，不要臆测
- 角色变化要有原文支撑
- 伏笔候选标注潜在的回收方向
- 完成后回复"提取完成"并总结提取条目数"""

DEEP_PROMPT = STANDARD_PROMPT + """

## 深度分析要求
- 分析伏笔之间的隐含关联
- 评估章节内容与已有设定的冲突点
- 标记可能被忽略的细节（可能发展为后续情节）
- 对角色行为的合理性给出判断"""

TOOLS = [
    get_chapter_context,
    save_character_changes,
    save_plot_facts,
    save_world_settings,
    save_foreshadowing_candidates,
]


class NovelExtractionService:
    async def extract(self, novel_id: int, chapter_id: int, user_id: int, mode: str = "standard") -> dict:
        state = NovelAgentState(
            novel_id=novel_id,
            chapter_id=chapter_id,
            user_id=user_id,
        )

        checkpointer = InMemorySaver()
        middleware = [logging_middleware]

        if mode == "deep":
            agent = create_novel_deep_agent(
                tools=TOOLS,
                system_prompt=DEEP_PROMPT,
                state_schema=NovelAgentState,
                checkpointer=checkpointer,
                middleware=middleware,
            )
        else:
            agent = create_novel_agent(
                model_type="flash",
                tools=TOOLS,
                system_prompt=STANDARD_PROMPT,
                state_schema=NovelAgentState,
                checkpointer=checkpointer,
                middleware=middleware,
            )

        try:
            result = await agent.ainvoke(
                {
                    "messages": [
                        {"role": "user", "content": f"请分析 novel_id={novel_id} 的第 {chapter_id} 章，提取所有结构化信息。"}
                    ],
                    "novel_id": novel_id,
                    "chapter_id": chapter_id,
                    "user_id": user_id,
                },
                config={"configurable": {"thread_id": f"extract-{novel_id}-{chapter_id}"}},
            )
        except Exception as e:
            logger.error("Agent invocation failed: novel_id=%s chapter_id=%s error=%s", novel_id, chapter_id, str(e))
            return {"chapter_summary": None, "pending_ids": [], "pending_count": 0, "error": str(e)}

        final_state = result.get("state", state)

        pending_ids = []
        async with async_session_factory() as db:
            repo = PendingMemoryRepo(db)
            for entry in final_state.pending_confirmations:
                pm = await repo.create(
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    memory_type=entry["memory_type"],
                    content=entry,
                )
                pending_ids.append(pm.id)

        summary = None
        last_msg = result["messages"][-1] if result.get("messages") else None
        if last_msg and hasattr(last_msg, "content"):
            summary = last_msg.content

        return {
            "chapter_summary": summary,
            "pending_ids": pending_ids,
            "pending_count": len(pending_ids),
        }
