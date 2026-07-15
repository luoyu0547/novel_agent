"""Phase 6 Author Studio — restricted intent protocol and agents.

Defines the StudioIntentAgent protocol, the production DeepSeekStudioIntentAgent,
and the StudioActionExecutor protocol. The intent agent interprets author text
into a restricted StudioIntent; the action executor dispatches permitted actions
to existing domain services.

Action vocabulary:
  AI-initiated: clarify, generate_plan, generate_brief, generate_context,
                generate_draft, review_draft, propose_revision, explain_sources
  Confirmation-only: accept, discard, apply_revision, force_accept, restore_version
"""

import json
import logging
from typing import Protocol, runtime_checkable

from langchain.chat_models import init_chat_model

from app.ai.config import FLASH_MODEL
from app.models.writing_session import WritingSession
from app.schemas.writing_studio import StudioAction, StudioActionResult, StudioIntent

logger = logging.getLogger("novel_agent.ai.studio_agent")

# System prompt for the intent classification agent
_INTENT_SYSTEM_PROMPT = """\
你是一个创作助手意图分类器。根据作者的输入文本和当前会话状态，判断作者想要执行的操作。

允许的 AI 操作（action 字段）：
- clarify: 需要澄清或无法确定意图
- generate_plan: 生成章节计划
- generate_brief: 生成章节简报
- generate_context: 生成上下文包
- generate_draft: 生成草稿
- review_draft: 审阅草稿
- propose_revision: 提出修改建议
- explain_sources: 解释引用来源

如果作者意图涉及确认操作（接受、丢弃、应用修订、强制接受、恢复版本），
请设置 confirmation_action 字段为以下之一：
- accept: 接受当前草稿
- discard: 丢弃当前草稿
- apply_revision: 应用修订
- force_accept: 强制接受
- restore_version: 恢复到之前的版本

请以 JSON 格式输出，包含以下字段：
{
  "action": "<上述 AI 操作之一>",
  "reply": "<对作者的简短回复>",
  "payload": {},
  "confirmation_action": null 或 "<上述确认操作之一>"
}
"""


@runtime_checkable
class StudioIntentAgent(Protocol):
    """Protocol for studio intent interpretation agents."""

    async def interpret(self, text: str, session: WritingSession) -> StudioIntent:
        ...


@runtime_checkable
class StudioActionExecutor(Protocol):
    """Protocol for studio action execution."""

    async def execute(
        self, session: WritingSession, intent: StudioIntent
    ) -> StudioActionResult:
        ...


class DeepSeekStudioIntentAgent:
    """Production intent agent using DeepSeek.

    Validates JSON output through StudioIntent; malformed output
    becomes a clarify response, never an unvalidated mutation.
    """

    def __init__(self):
        self._model = init_chat_model(FLASH_MODEL, model_provider="deepseek")

    async def interpret(self, text: str, session: WritingSession) -> StudioIntent:
        session_info = (
            f"会话ID: {session.id}, "
            f"状态: {session.status}, "
            f"活跃写作运行ID: {session.active_writing_run_id}"
        )
        user_message = f"当前会话: {session_info}\n作者输入: {text}"

        try:
            response = await self._model.ainvoke(
                [
                    {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ]
            )
            raw = response.content
            # Strip markdown code fences if present
            if raw.startswith("```"):
                lines = raw.split("\n")
                # Remove first and last lines (code fence markers)
                lines = [l for l in lines if not l.strip().startswith("```")]
                raw = "\n".join(lines)
            parsed = json.loads(raw)
            return StudioIntent.model_validate(parsed)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("StudioIntent validation failed, falling back to clarify: %s", exc)
            return StudioIntent(
                action="clarify",
                reply="抱歉，我无法理解您的请求，请重新描述。",
                payload={"raw_error": str(exc)},
            )
