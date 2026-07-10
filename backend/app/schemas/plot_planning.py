from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

PlotUnitStatus = Literal["draft", "active", "completed", "archived"]
PlotPlanRevisionStatus = Literal["draft", "active", "stale", "blocked", "superseded", "completed"]
PlanningDecisionStatus = Literal["pending", "resolved", "superseded"]
PlanningDecisionSource = Literal["during_generation", "during_review"]
DraftRevisionStatus = Literal["candidate", "applied", "superseded"]


class AuthorFoundationOut(BaseModel):
    id: int
    novel_id: int
    outline: str
    current_intent: str
    stage_goal: str
    constraints_json: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuthorFoundationUpdateRequest(BaseModel):
    outline: Optional[str] = None
    current_intent: Optional[str] = None
    stage_goal: Optional[str] = None
    constraints_json: Optional[dict[str, Any]] = None


class AuthorFoundationRevisionOut(BaseModel):
    id: int
    novel_id: int
    foundation_id: int
    version: int
    snapshot_json: dict[str, Any]
    change_reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PlotUnitCreateRequest(BaseModel):
    title: str
    scope_type: str
    start_position: int
    end_position: int
    author_goal: str = ""
    start_state: str = ""
    end_state: str = ""


class PlotUnitOut(BaseModel):
    id: int
    novel_id: int
    title: str
    scope_type: str
    start_position: int
    end_position: int
    author_goal: str
    start_state: str
    end_state: str
    foundation_revision_id: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlotPlanRevisionOut(BaseModel):
    id: int
    novel_id: int
    plot_unit_id: int
    version: int
    foundation_revision_id: int
    based_on_published_chapter_id: Optional[int] = None
    plan_json: dict[str, Any]
    change_reason: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlanningDecisionOut(BaseModel):
    id: int
    novel_id: int
    plot_unit_id: Optional[int] = None
    plot_plan_revision_id: Optional[int] = None
    chapter_brief_id: Optional[int] = None
    writing_run_id: Optional[int] = None
    source: str
    status: str
    conflict_summary: str
    evidence_json: dict[str, Any]
    options_json: list
    recommended_index: int
    recommendation_reason: str
    impact_scope_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DecisionOptionOut(BaseModel):
    label: str
    consequence: str


class ChooseDecisionRequest(BaseModel):
    option_index: Optional[int] = None
    custom_intent: Optional[str] = None

    @model_validator(mode="after")
    def require_option_or_custom_intent(self):
        if self.option_index is None and not self.custom_intent:
            raise ValueError("必须提供 option_index 或 custom_intent")
        if self.option_index is not None and self.custom_intent:
            raise ValueError("不能同时提供 option_index 和 custom_intent")
        return self


class DraftRevisionOut(BaseModel):
    id: int
    novel_id: int
    writing_run_id: Optional[int] = None
    parent_revision_id: Optional[int] = None
    decision_id: Optional[int] = None
    base_content: str
    candidate_content: str
    scope_json: dict[str, Any]
    diff_json: dict[str, Any]
    reason: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
