"""Real Phase 2 quality gate checkers backed by DeepSeek.

One explicit checker per quality dimension, invoked sequentially behind a common
protocol. Each checker receives only the draft, brief, context and its rubric and
returns one or more ``CheckResult`` objects. A provider/parse failure raises so the
``QualityGateService`` can convert it into a ``gated=False`` diagnostic result.
"""

import abc
import json
import logging
from typing import Optional

from pydantic import BaseModel

from app.ai.agent import create_novel_agent
from app.ai.models import NovelAgentState
from app.ai.quality_gate import AGENT_TYPES, BaseQualityGateAgent, CheckResult

logger = logging.getLogger("novel_agent.ai.quality_agents")

ALLOWED_SEVERITIES = {"blocking", "major", "minor"}
ALLOWED_RESOLUTION_MODES = {"auto_fixable", "needs_intent"}


class _ParsedItem(BaseModel):
    model_config = {"extra": "ignore"}

    passed: bool
    severity: str
    resolution_mode: str = "auto_fixable"
    fix_strategy: Optional[str] = None
    fixed_text: Optional[str] = None
    fix_description: str = ""
    options: Optional[list[dict]] = None
    intent_type: Optional[str] = None
    description: str = ""
    location: str = ""
    context: str = ""


def parse_check_results(raw: str, issue_type: str) -> list[CheckResult]:
    """Validate a raw model response into ``CheckResult`` objects.

    Ignores unknown fields. Raises ``ValueError``/``ValidationError`` on malformed
    JSON, missing required fields or an invalid severity/resolution_mode so the
    service can convert the failure into a ``gated=False`` diagnostic instead of
    crashing the run.

    Validation rules:
    - severity must be one of: blocking, major, minor
    - resolution_mode must be one of: auto_fixable, needs_intent
    - fix_strategy is legal only for auto_fixable
    - options/intent_type are legal only for needs_intent
    """
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("expected a JSON array or object")

    results: list[CheckResult] = []
    for item in data:
        parsed = _ParsedItem.model_validate(item)
        if parsed.severity not in ALLOWED_SEVERITIES:
            raise ValueError(f"invalid severity: {parsed.severity}")
        if parsed.resolution_mode not in ALLOWED_RESOLUTION_MODES:
            raise ValueError(f"invalid resolution_mode: {parsed.resolution_mode}")
        # fix_strategy is legal only for auto_fixable
        if parsed.resolution_mode != "auto_fixable" and parsed.fix_strategy:
            raise ValueError("fix_strategy is legal only for auto_fixable")
        # options/intent_type are legal only for needs_intent
        if parsed.resolution_mode != "needs_intent" and (parsed.options or parsed.intent_type):
            raise ValueError("options/intent_type are legal only for needs_intent")
        results.append(
            CheckResult(
                issue_type=issue_type,
                passed=parsed.passed,
                severity=parsed.severity,
                resolution_mode=parsed.resolution_mode,
                fix_strategy=parsed.fix_strategy,
                fixed_text=parsed.fixed_text,
                fix_description=parsed.fix_description,
                options=parsed.options,
                intent_type=parsed.intent_type,
                description=parsed.description,
                location=parsed.location,
                context=parsed.context,
            )
        )
    return results


class BaseQualityChecker(abc.ABC):
    """Common protocol for a single quality dimension checker."""

    issue_type: str = ""
    rubric: str = ""

    async def check(self, draft: str, brief: dict, context: dict) -> list[CheckResult]:
        prompt = self._build_prompt(draft, brief, context)
        raw = await self._call_llm_json(prompt)
        return parse_check_results(raw, self.issue_type)

    def _build_prompt(self, draft: str, brief: dict, context: dict) -> str:
        brief_text = json.dumps(brief, ensure_ascii=False)
        context_text = json.dumps(context, ensure_ascii=False)
        return f"""你是一名严格的小说质量审稿编辑，只负责以下维度的审查：

审查维度：{self.issue_type}
审查标准：{self.rubric}

章节任务书：{brief_text}
上下文（角色/世界观/前文摘要等）：{context_text}

草稿正文：
{draft}

请只针对该维度输出审阅结果，以 JSON 数组返回，每个元素字段如下：
- passed: 布尔，该维度是否通过
- severity: 影响程度，"blocking"（阻塞验收）、"major"（重大问题）或 "minor"（轻微问题）
- resolution_mode: "auto_fixable"（可自动修复）或 "needs_intent"（需要作者意图）
- fix_strategy: 可选，"full_rewrite"（整体重写）或 "local_replace"（局部替换），仅 auto_fixable 时有效
- fixed_text: 可选，局部替换时的新文本
- fix_description: 可选，修复说明
- options: 可选，needs_intent 时的候选方案数组，每个元素含 label 与 summary
- intent_type: 可选，needs_intent 时的意图类型（如 choice、freeform）
- description: 问题描述
- location: 问题在草稿中的位置或原文片段
- context: 相关上下文片段

若该维度通过，返回 [{{"passed": true, "severity": "minor", "resolution_mode": "auto_fixable"}}]。
只返回 JSON，不要其他内容。"""

    async def _call_llm_json(self, prompt: str) -> str:
        agent = create_novel_agent(
            model_type="flash",
            tools=[],
            system_prompt="你是一个小说质量审稿AI，只返回JSON格式的审阅结果。",
            state_schema=NovelAgentState,
        )
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}], "novel_id": 0, "chapter_id": 0, "user_id": 0, "pending_confirmations": []},
            {"configurable": {"thread_id": f"quality-gate-{self.issue_type}"}},
        )
        return result["messages"][-1].content if result.get("messages") else "[]"


class TaskCompletionChecker(BaseQualityChecker):
    issue_type = "task_completion"
    rubric = "草稿是否完成章节任务书中的剧情任务、角色任务、信息任务与验收标准，不得遗漏关键任务或偏离任务书。"


class StyleChecker(BaseQualityChecker):
    issue_type = "style"
    rubric = "文风是否符合风格指南与叙事视角，可读性、节奏与语言质感是否达标，避免口语化、重复说明或大纲化表达。"


class CharacterChecker(BaseQualityChecker):
    issue_type = "character"
    rubric = "角色言行是否符合既定人设、性格与行为规则，角色弧光是否连贯，有无人设崩塌或动机缺失。"


class ContinuityChecker(BaseQualityChecker):
    issue_type = "continuity"
    rubric = "剧情连贯性：与前文是否衔接、有无逻辑断裂、时间线/因果是否自洽、有无前后矛盾。"


class WorldChecker(BaseQualityChecker):
    issue_type = "world"
    rubric = "世界观一致性：设定、规则、势力、地理与历史是否与既定世界观相符，有无违反世界规则之处。"


class ForeshadowingChecker(BaseQualityChecker):
    issue_type = "foreshadowing"
    rubric = "伏笔的埋设、发展与呼应是否合理，有无悬置未回的伏笔或突兀的转折，伏笔状态是否与上下文一致。"


class LengthChecker(BaseQualityChecker):
    issue_type = "length"
    rubric = "篇幅与内容密度是否满足篇幅契约，字数增长是否来自有效场景、动作、心理、对话与细节，而非重复说明。"


def default_checkers() -> list[BaseQualityChecker]:
    return [
        TaskCompletionChecker(),
        StyleChecker(),
        CharacterChecker(),
        ContinuityChecker(),
        WorldChecker(),
        ForeshadowingChecker(),
        LengthChecker(),
    ]


class DeepSeekQualityGateAgent(BaseQualityGateAgent):
    """Sequential DeepSeek-backed quality gate: one checker per AGENT_TYPE."""

    def __init__(self, checkers: Optional[list[BaseQualityChecker]] = None):
        self.checkers = list(checkers) if checkers is not None else default_checkers()
        wired = {c.issue_type for c in self.checkers}
        missing = set(AGENT_TYPES) - wired
        if missing:
            raise ValueError(f"missing checkers for: {sorted(missing)}")

    async def check(self, draft: str, brief: dict, context_package: dict) -> list[CheckResult]:
        results: list[CheckResult] = []
        for checker in self.checkers:
            results.extend(await checker.check(draft, brief, context_package))
        return results
