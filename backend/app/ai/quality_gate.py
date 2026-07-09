import abc
from typing import Optional

from pydantic import BaseModel


class CheckResult(BaseModel):
    passed: bool
    issue_type: str
    severity: str  # "auto_fixable" | "needs_intent"
    fix_strategy: Optional[str] = None  # "full_rewrite" | "local_replace" | None
    fixed_text: Optional[str] = None
    fix_description: str = ""
    options: Optional[list[dict]] = None
    intent_type: Optional[str] = None
    description: str = ""
    location: str = ""
    context: str = ""


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
            CheckResult(passed=True, issue_type=t, severity="auto_fixable", fix_strategy="local_replace")
            for t in AGENT_TYPES
        ]
