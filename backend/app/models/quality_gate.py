import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReviewIssue(Base):
    """质量门禁产生的可追踪审阅问题。"""

    __tablename__ = "review_issues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    writing_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("writing_runs.id"), nullable=True)
    issue_type: Mapped[str] = mapped_column(nullable=False)
    severity: Mapped[str] = mapped_column(nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    related_memory: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    acceptance_blocking: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(default="open")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
