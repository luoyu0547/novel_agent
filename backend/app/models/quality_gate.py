import datetime
from typing import Optional

from sqlalchemy import ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReviewIssue(Base):
    """质量门禁产生的可追踪审阅问题。"""

    __tablename__ = "review_issues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )
    writing_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("writing_runs.id"), nullable=True
    )
    issue_type: Mapped[str] = mapped_column(nullable=False)
    severity: Mapped[str] = mapped_column(nullable=False)
    resolution_mode: Mapped[str] = mapped_column(nullable=False, default="needs_intent")
    location: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    related_memory: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    repair_options_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    resolved_by_revision_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("draft_revisions.id"), nullable=True
    )
    ignored_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acceptance_blocking: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(default="open")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
