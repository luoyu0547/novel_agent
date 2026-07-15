"""Pydantic schemas for Phase 6 Author Studio (Writing Studio)."""

from typing import Literal

from pydantic import BaseModel, Field


# ── AI intent protocol models ────────────────────────────────────────────

StudioAction = Literal[
    "clarify", "generate_plan", "generate_brief", "generate_context",
    "generate_draft", "review_draft", "propose_revision", "explain_sources",
]

ConfirmationAction = Literal[
    "accept", "discard", "apply_revision", "force_accept", "restore_version",
]


class StudioIntent(BaseModel):
    action: StudioAction
    reply: str
    payload: dict = Field(default_factory=dict)
    confirmation_action: ConfirmationAction | None = None


class StudioActionResult(BaseModel):
    message_type: str
    content_json: dict
    writing_run_id: int | None = None
    context_package_id: int | None = None
    draft_version_id: int | None = None


# ── Request models ─────────────────────────────────────────────────────


class CreateWritingSessionRequest(BaseModel):
    title: str = Field(default="新创作会话", min_length=1, max_length=200)
    target_chapter_id: int | None = None


class StudioMessageCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    idempotency_key: str = Field(min_length=1, max_length=128)


class StudioActionRequest(BaseModel):
    action: Literal[
        "accept", "discard", "apply_revision", "force_accept", "restore_version"
    ]
    payload: dict = Field(default_factory=dict)


class WorkingCopySaveRequest(BaseModel):
    title: str = Field(max_length=500)
    content: str
    base_revision_sequence: int = Field(ge=0)


# ── Response models ────────────────────────────────────────────────────


class StudioSourceOut(BaseModel):
    source_id: str
    source_type: str
    title: str
    locator: dict
    preview: str
    inclusion_reason: str


class WritingSessionOut(BaseModel):
    id: int
    novel_id: int
    target_chapter_id: int | None
    active_writing_run_id: int | None
    title: str
    status: str
    model_config = {"from_attributes": True}


class WritingMessageOut(BaseModel):
    id: int
    session_id: int
    role: Literal["author", "assistant", "system"]
    message_type: str
    content_json: dict
    action_status: Literal["running", "completed", "needs_confirmation", "failed"]
    writing_run_id: int | None
    context_package_id: int | None
    draft_version_id: int | None
    model_config = {"from_attributes": True}


class DraftWorkingCopyOut(BaseModel):
    writing_run_id: int
    draft_version_id: int
    title: str
    content: str
    base_revision_sequence: int
    model_config = {"from_attributes": True}


class StudioWorkspaceOut(BaseModel):
    session: WritingSessionOut
    messages: list[WritingMessageOut]
    working_copy: DraftWorkingCopyOut | None


class StudioMessageResult(BaseModel):
    assistant_message: WritingMessageOut
    workspace: StudioWorkspaceOut
