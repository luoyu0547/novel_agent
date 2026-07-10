import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VolumeArc(Base):
    """卷弧模型。status: draft | active | archived。"""

    __tablename__ = "volume_arcs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    blueprint_id: Mapped[Optional[int]] = mapped_column(ForeignKey("novel_blueprints.id"), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    start_state: Mapped[str] = mapped_column(Text, nullable=False, default="")
    end_state: Mapped[str] = mapped_column(Text, nullable=False, default="")
    key_events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    pacing_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    foreshadowing_plan: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(default="draft")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)


class PlanVersion(Base):
    """计划版本快照模型。status: current | archived。"""

    __tablename__ = "plan_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    plan_type: Mapped[str] = mapped_column(nullable=False)
    plan_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    impact_scope: Mapped[str] = mapped_column(Text, nullable=False, default="")
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(default="current")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)


class ReviewIssue(Base):
    """审阅问题模型。status: open | resolved | dismissed。"""

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
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)
