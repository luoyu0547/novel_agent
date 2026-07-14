"""Pydantic protocol models for Phase 3 structured AI output."""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AIProtocolError(Exception):
    """Raised when AI output fails Pydantic validation or JSON parse."""


class DecisionOption(BaseModel):
    label: str = Field(min_length=1)
    action: str = Field(min_length=1)
    consequence: str = Field(min_length=1)
    affected_future_scope: dict[str, Any] = Field(default_factory=dict)


class ConflictOutput(BaseModel):
    source: Literal["during_generation", "during_review"]
    core_conflict: str = Field(min_length=1)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    options: list[DecisionOption]
    recommended_index: int = Field(ge=0)
    recommendation_reason: str = Field(min_length=1)
    impact_scope: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_options(self):
        labels = [f"{item.label}:{item.action}" for item in self.options]
        if len(self.options) not in (2, 3) or len(set(labels)) != len(labels):
            raise ValueError("必须提供 2-3 个不同的真实方案")
        if self.recommended_index >= len(self.options):
            raise ValueError("推荐方案索引越界")
        return self


class DraftGenerationOutput(BaseModel):
    status: Literal["draft_ready", "decision_required", "unsafe_planning"]
    draft: str = ""
    conflict: ConflictOutput | None = None
    unsafe_reason: str | None = None


class PlotPlanOutput(BaseModel):
    starting_state: str = Field(min_length=1)
    stage_goal: str = Field(min_length=1)
    core_conflict: str = Field(min_length=1)
    key_turns: list[dict[str, Any]] = Field(min_length=1)
    progression: list[dict[str, Any]] = Field(min_length=1)
    character_changes: list[dict[str, Any]] = Field(default_factory=list)
    foreshadowing: list[dict[str, Any]] = Field(default_factory=list)
    must_complete: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(min_length=1)


class QualityIssueOutput(BaseModel):
    """Typed quality issue from draft review, with independent severity and resolution_mode."""
    issue_type: str = "unknown"
    severity: Literal["blocking", "major", "minor"] = "major"
    resolution_mode: Literal["auto_fixable", "needs_intent"] = "auto_fixable"
    location: str = ""
    description: str = ""
    related_memory: str | None = None
    suggestion: str = ""
    acceptance_blocking: bool = False


class DraftReviewOutput(BaseModel):
    narrative_conflicts: list[ConflictOutput] = Field(default_factory=list)
    quality_issues: list[QualityIssueOutput] = Field(default_factory=list)
    has_continuity_conflicts: bool = False
    verdict: Literal["pass", "revise"] = "pass"


class LocalRevisionOutput(BaseModel):
    candidate_content: str = Field(min_length=1)
    scope: dict[str, Any]
    diff: dict[str, Any]
    plan_patch: dict[str, Any]
    expanded_scope: bool = False
    expansion_reason: str = ""
