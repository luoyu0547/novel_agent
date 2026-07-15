import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NovelBlueprint(Base):
    __tablename__ = "novel_blueprints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(default="draft")
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    novel = relationship("Novel", back_populates="blueprints")


class ChapterPlan(Base):
    __tablename__ = "chapter_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(default="draft")
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)


class ChapterBrief(Base):
    __tablename__ = "chapter_briefs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_plan_id: Mapped[int] = mapped_column(ForeignKey("chapter_plans.id"), nullable=False)
    chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    status: Mapped[str] = mapped_column(default="draft")
    brief_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    length_contract_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)


class ContextPackage(Base):
    __tablename__ = "context_packages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_brief_id: Mapped[int] = mapped_column(ForeignKey("chapter_briefs.id"), nullable=False)
    package_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)


class WritingRun(Base):
    __tablename__ = "writing_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_brief_id: Mapped[int] = mapped_column(ForeignKey("chapter_briefs.id"), nullable=False)
    context_package_id: Mapped[int] = mapped_column(ForeignKey("context_packages.id"), nullable=False)
    target_chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    status: Mapped[str] = mapped_column(default="running")
    draft_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gate_result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    gated: Mapped[bool] = mapped_column(default=False)
    has_pending_repairs: Mapped[bool] = mapped_column(default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    accepted_at: Mapped[Optional[datetime.datetime]] = mapped_column(nullable=True)
    decision_id: Mapped[Optional[int]] = mapped_column(ForeignKey("planning_decisions.id"), nullable=True)
    writing_session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("writing_sessions.id"), nullable=True, index=True)
    context_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    planning_blocked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)


class RepairLog(Base):
    __tablename__ = "repair_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    writing_run_id: Mapped[int] = mapped_column(ForeignKey("writing_runs.id"), nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(Text, nullable=False, default="")
    old_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    new_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)


class PendingRepair(Base):
    __tablename__ = "pending_repairs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    writing_run_id: Mapped[int] = mapped_column(ForeignKey("writing_runs.id"), nullable=False, index=True)
    review_issue_id: Mapped[Optional[int]] = mapped_column(ForeignKey("review_issues.id"), nullable=True)
    issue_type: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(Text, nullable=False, default="")
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    intent_type: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="pending")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
