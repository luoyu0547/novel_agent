from datetime import datetime

from pydantic import BaseModel


class PendingMemoryOut(BaseModel):
    id: int
    novel_id: int
    chapter_id: int
    memory_type: str
    content: dict
    status: str
    created_at: datetime


class PendingMemoryBatchBody(BaseModel):
    ids: list[int]
    action: str  # "confirm" | "reject"


class ExtractResponse(BaseModel):
    chapter_summary: str | None = None
    pending_ids: list[int] = []
    pending_count: int = 0


class ExtractRequest(BaseModel):
    mode: str = "standard"  # "standard" | "deep"
