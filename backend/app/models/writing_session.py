"""Phase 6 Author Studio — WritingSession, WritingMessage, DraftWorkingCopy models."""

import datetime

from sqlalchemy import ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WritingSession(Base):
    __tablename__ = "writing_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    target_chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    active_writing_run_id: Mapped[int | None] = mapped_column(ForeignKey("writing_runs.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="新创作会话")
    status: Mapped[str] = mapped_column(nullable=False, default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)


class WritingMessage(Base):
    __tablename__ = "writing_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("writing_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(nullable=False)
    message_type: Mapped[str] = mapped_column(nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    action_status: Mapped[str] = mapped_column(nullable=False, default="completed")
    idempotency_key: Mapped[str | None] = mapped_column(nullable=True, unique=True)
    writing_run_id: Mapped[int | None] = mapped_column(ForeignKey("writing_runs.id"), nullable=True)
    context_package_id: Mapped[int | None] = mapped_column(ForeignKey("context_packages.id"), nullable=True)
    draft_version_id: Mapped[int | None] = mapped_column(ForeignKey("draft_versions.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)


class DraftWorkingCopy(Base):
    __tablename__ = "draft_working_copies"

    writing_run_id: Mapped[int] = mapped_column(ForeignKey("writing_runs.id"), primary_key=True)
    draft_version_id: Mapped[int] = mapped_column(ForeignKey("draft_versions.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_revision_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)
