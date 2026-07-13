"""Phase 4 辅助修订——Pydantic schemas for DraftVersion operations and review flows."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ── Type literals ──

DraftVersionStatus = Literal["draft", "accepted", "rejected", "archived"]
DraftRevisionStatus = Literal["candidate", "applied", "rejected", "superseded"]
DraftRevisionSource = Literal[
    "planning_decision", "review_issue", "author_request", "manual_edit", "restore"
]
IssueSeverity = Literal["blocking", "major", "minor"]
IssueResolutionMode = Literal["auto_fixable", "needs_intent"]


# ── Response models ──


class DraftVersionOut(BaseModel):
    id: int
    novel_id: int
    chapter_id: Optional[int] = None
    writing_run_id: int
    based_on_version_id: Optional[int] = None
    version: int
    title: str
    content: str
    word_count: int
    change_reason: str
    status: str
    revision_sequence: int
    acceptance_override_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DraftRevisionOut(BaseModel):
    id: int
    novel_id: int
    writing_run_id: Optional[int] = None
    draft_version_id: Optional[int] = None
    parent_revision_id: Optional[int] = None
    decision_id: Optional[int] = None
    sequence: int
    source_type: str
    source_id: Optional[int] = None
    base_revision_sequence: int
    base_content_hash: str
    base_content: str
    candidate_content: str
    patches_json: list
    scope_json: dict[str, Any]
    diff_json: dict[str, Any]
    reason: str
    expanded_scope: bool = False
    expanded_scope_reason: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewIssueOut(BaseModel):
    id: int
    novel_id: int
    chapter_id: Optional[int] = None
    writing_run_id: Optional[int] = None
    issue_type: str
    severity: str
    resolution_mode: str
    location: str
    description: str
    related_memory: Optional[str] = None
    suggestion: str
    repair_options_json: Optional[list] = None
    resolved_by_revision_id: Optional[int] = None
    ignored_reason: Optional[str] = None
    acceptance_blocking: bool
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepairOptionOut(BaseModel):
    option_index: int
    label: str
    description: str


# ── Request models ──


class CreateDraftVersionRequest(BaseModel):
    based_on_version_id: int
    change_reason: str = Field(min_length=1, max_length=500)


class RestoreVersionRequest(BaseModel):
    base_revision_sequence: int = Field(ge=0)
    change_reason: str = Field(default="恢复历史版本", min_length=1, max_length=500)


class ManualRevisionRequest(BaseModel):
    content: str
    change_reason: str = Field(min_length=1, max_length=500)
    base_revision_sequence: int = Field(ge=0)


class CreateRevisionRequest(BaseModel):
    option_index: int | None = Field(default=None, ge=0)
    custom_intent: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_exactly_one_direction(self):
        if (self.option_index is None) == (self.custom_intent is None):
            raise ValueError("必须且只能提供 option_index 或 custom_intent")
        return self


class IgnoreIssueRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ApplyRevisionRequest(BaseModel):
    confirm_expanded_scope: bool = False


class AcceptWritingRunRequest(BaseModel):
    force_accept: bool = False
    force_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_force_reason(self):
        if self.force_accept and not self.force_reason:
            raise ValueError("强制接受必须填写原因")
        if not self.force_accept and self.force_reason:
            raise ValueError("未强制接受时不能填写强制原因")
        return self
