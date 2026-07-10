from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class VolumeArcOut(BaseModel):
    id: int
    novel_id: int
    blueprint_id: Optional[int] = None
    order_index: int
    title: str
    goal: str
    start_state: str
    end_state: str
    key_events: list[Any]
    pacing_notes: str
    foreshadowing_plan: Any
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VolumeArcCreateRequest(BaseModel):
    blueprint_id: Optional[int] = None
    order_index: int = 0
    title: str = ""
    goal: str = ""
    start_state: str = ""
    end_state: str = ""
    key_events: list[Any] = []
    pacing_notes: str = ""
    foreshadowing_plan: Any = []
    status: str = "draft"


class VolumeArcUpdateRequest(BaseModel):
    blueprint_id: Optional[int] = None
    order_index: Optional[int] = None
    title: Optional[str] = None
    goal: Optional[str] = None
    start_state: Optional[str] = None
    end_state: Optional[str] = None
    key_events: Optional[list[Any]] = None
    pacing_notes: Optional[str] = None
    foreshadowing_plan: Optional[Any] = None
    status: Optional[str] = None


class PlanVersionOut(BaseModel):
    id: int
    novel_id: int
    plan_type: str
    plan_id: int
    version: int
    change_reason: str
    impact_scope: str
    snapshot_json: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlanVersionCreateRequest(BaseModel):
    plan_type: str
    plan_id: int
    change_reason: str = ""
    impact_scope: str = ""
    snapshot_json: dict[str, Any] = {}


class ReviewIssueOut(BaseModel):
    id: int
    novel_id: int
    writing_run_id: Optional[int] = None
    issue_type: str
    severity: str
    location: str
    description: str
    related_memory: Optional[str] = None
    suggestion: str
    acceptance_blocking: bool = True
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewIssueCreateRequest(BaseModel):
    writing_run_id: Optional[int] = None
    issue_type: str
    severity: str
    location: str = ""
    description: str = ""
    related_memory: Optional[str] = None
    suggestion: str = ""
    acceptance_blocking: bool = True


class ReviewIssueResolveRequest(BaseModel):
    status: str = "resolved"
