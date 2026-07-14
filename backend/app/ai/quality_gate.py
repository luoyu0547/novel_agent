import abc
from typing import Literal, Optional

from pydantic import BaseModel


class CheckResult(BaseModel):
    passed: bool
    issue_type: str
    severity: Literal["blocking", "major", "minor"] = "major"
    resolution_mode: Literal["auto_fixable", "needs_intent"] = "auto_fixable"
    fix_strategy: Optional[str] = None  # "full_rewrite" | "local_replace" | None, only for auto_fixable
    fixed_text: Optional[str] = None  # only for local_replace
    fix_description: str = ""
    options: Optional[list[dict]] = None  # only for needs_intent
    intent_type: Optional[str] = None  # only for needs_intent
    description: str = ""
    location: str = ""
    context: str = ""
    suggestion: str = ""


AGENT_TYPES = [
    "task_completion",
    "style",
    "character",
    "continuity",
    "world",
    "foreshadowing",
    "length",
]


class BaseQualityGateAgent(abc.ABC):
    @abc.abstractmethod
    async def check(self, draft: str, brief: dict, context_package: dict) -> list[CheckResult]:
        ...


class FakeQualityGateAgent(BaseQualityGateAgent):
    async def check(self, draft: str, brief: dict, context_package: dict) -> list[CheckResult]:
        return [
            CheckResult(passed=True, issue_type=t, severity="minor", resolution_mode="auto_fixable")
            for t in AGENT_TYPES
        ]


# Imported at the bottom to avoid a circular import: quality_agents imports the
# names defined above (CheckResult, AGENT_TYPES, BaseQualityGateAgent).
from app.ai.quality_agents import DeepSeekQualityGateAgent  # noqa: E402, F401

__all__ = [
    "CheckResult",
    "AGENT_TYPES",
    "BaseQualityGateAgent",
    "FakeQualityGateAgent",
    "DeepSeekQualityGateAgent",
]
