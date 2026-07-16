"""Pydantic schemas for retrieval index API endpoints."""
import datetime
from typing import Optional

from pydantic import BaseModel


class RetrievalIndexStatusOut(BaseModel):
    """Output schema for the retrieval index status endpoint."""

    status: str
    operation: str
    requested_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    last_error: Optional[str] = None

    model_config = {"from_attributes": True}


class RetrievalRebuildOut(BaseModel):
    """Output schema for the retrieval index rebuild endpoint."""

    job_id: int
    status: str
