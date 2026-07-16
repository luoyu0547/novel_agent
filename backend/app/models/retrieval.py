"""Retrieval index job model for durable background indexing/purging."""
import datetime
from typing import Optional

from sqlalchemy import Index, String, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

OPERATIONS = {"sync", "rebuild", "purge"}
ACTIVE_STATUSES = {"pending", "running", "retry_wait"}


class RetrievalIndexJob(Base):
    """Durable job record for retrieval index operations.

    No foreign key to novels — a queued purge can outlive the novel row.
    novel_id is nullable so that purge jobs can still run after novel deletion.
    """

    __tablename__ = "retrieval_index_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    tenant_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    lease_expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.now
    )
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now, onupdate=datetime.datetime.now
    )

    __table_args__ = (
        Index(
            "ix_retrieval_jobs_claimable",
            "status",
            "next_attempt_at",
            "requested_at",
        ),
    )
