from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class NovelBlueprintOut(BaseModel):
    id: int
    novel_id: int
    version: int
    status: str
    content_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BlueprintGenerateRequest(BaseModel):
    author_input: str


class BlueprintUpdateRequest(BaseModel):
    content_json: Optional[dict[str, Any]] = None


class ChapterPlanOut(BaseModel):
    id: int
    novel_id: int
    chapter_id: Optional[int] = None
    position: int
    status: str
    content_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterPlanUpdateRequest(BaseModel):
    content_json: Optional[dict[str, Any]] = None


class ChapterBriefOut(BaseModel):
    id: int
    novel_id: int
    chapter_plan_id: int
    chapter_id: Optional[int] = None
    status: str
    brief_json: dict[str, Any]
    length_contract_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterBriefGenerateRequest(BaseModel):
    chapter_plan_id: int
    plot_plan_revision_id: Optional[int] = None
    author_input: Optional[str] = None


class ChapterBriefUpdateRequest(BaseModel):
    brief_json: Optional[dict[str, Any]] = None
    length_contract_json: Optional[dict[str, Any]] = None


class ContextPackageGenerateRequest(BaseModel):
    chapter_brief_id: int
    plot_plan_revision_id: Optional[int] = None
    author_input: Optional[str] = None


class ContextPackageOut(BaseModel):
    id: int
    novel_id: int
    chapter_brief_id: int
    package_json: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class WritingRunOut(BaseModel):
    id: int
    novel_id: int
    chapter_brief_id: int
    context_package_id: int
    target_chapter_id: Optional[int] = None
    status: str
    draft_content: str
    word_count: int
    gate_result_json: dict[str, Any]
    gated: bool = False
    has_pending_repairs: bool = False
    error_message: Optional[str] = None
    accepted_at: Optional[datetime] = None
    decision_id: Optional[int] = None
    context_snapshot_json: dict[str, Any] = {}
    planning_blocked: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WritingRunCreateRequest(BaseModel):
    chapter_brief_id: int
    context_package_id: Optional[int] = None
    plot_plan_revision_id: Optional[int] = None
    author_input: Optional[str] = None


class RepairLogOut(BaseModel):
    id: int
    novel_id: int
    writing_run_id: int
    issue_type: str
    description: str
    location: str
    old_text: str
    new_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PendingRepairOut(BaseModel):
    id: int
    novel_id: int
    chapter_id: Optional[int] = None
    writing_run_id: int
    issue_type: str
    description: str
    location: str
    context: str
    options: Optional[list] = None
    intent_type: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResolveRepairRequest(BaseModel):
    action: str = Field(...)  # "apply"
    choice_index: Optional[int] = None
    intent_text: Optional[str] = None


class RepairsResponse(BaseModel):
    repair_logs: list[RepairLogOut]
    pending_repairs: list[PendingRepairOut]
