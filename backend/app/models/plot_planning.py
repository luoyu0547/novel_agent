import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AuthorFoundation(Base):
    __tablename__ = "author_foundations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, unique=True, index=True)
    outline: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_intent: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stage_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    constraints_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    novel = relationship("Novel", back_populates="author_foundation")


class AuthorFoundationRevision(Base):
    __tablename__ = "author_foundation_revisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    foundation_id: Mapped[int] = mapped_column(ForeignKey("author_foundations.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)


class PlotUnit(Base):
    __tablename__ = "plot_units"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    scope_type: Mapped[str] = mapped_column(nullable=False)
    start_position: Mapped[int] = mapped_column(Integer, nullable=False)
    end_position: Mapped[int] = mapped_column(Integer, nullable=False)
    author_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    start_state: Mapped[str] = mapped_column(Text, nullable=False, default="")
    end_state: Mapped[str] = mapped_column(Text, nullable=False, default="")
    foundation_revision_id: Mapped[int] = mapped_column(ForeignKey("author_foundation_revisions.id"), nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="draft")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    novel = relationship("Novel", back_populates="plot_units")


class PlotPlanRevision(Base):
    __tablename__ = "plot_plan_revisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    plot_unit_id: Mapped[int] = mapped_column(ForeignKey("plot_units.id"), nullable=False, index=True)
    foundation_revision_id: Mapped[int] = mapped_column(ForeignKey("author_foundation_revisions.id"), nullable=False)
    based_on_published_chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(nullable=False, default="draft")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)


class PlanningDecision(Base):
    __tablename__ = "planning_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    plot_unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("plot_units.id"), nullable=True)
    plot_plan_revision_id: Mapped[Optional[int]] = mapped_column(ForeignKey("plot_plan_revisions.id"), nullable=True)
    chapter_brief_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapter_briefs.id"), nullable=True)
    writing_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("writing_runs.id"), nullable=True)
    source: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="pending")
    conflict_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    options_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommended_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommendation_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    impact_scope_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    selected_option_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    custom_intent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)


class DraftRevision(Base):
    __tablename__ = "draft_revisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    writing_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("writing_runs.id"), nullable=True)
    parent_revision_id: Mapped[Optional[int]] = mapped_column(ForeignKey("draft_revisions.id"), nullable=True)
    decision_id: Mapped[Optional[int]] = mapped_column(ForeignKey("planning_decisions.id"), nullable=True)
    base_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    candidate_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    scope_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    diff_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(nullable=False, default="candidate")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)
