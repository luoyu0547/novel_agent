"""Phase 4 辅助修订——DraftVersion 模型。

DraftVersion 作为 WritingRun 的版本层，每次自动生成或手动修订均创建新版本。
版本号在 WritingRun 域内单调递增。"""

import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DraftVersion(Base):
    """写作运行中的版本快照，对应一次完整的生成或修订结果。"""

    __tablename__ = "draft_versions"
    __table_args__ = (
        UniqueConstraint(
            "writing_run_id", "version", name="uq_draft_versions_run_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id"), nullable=False, index=True
    )
    chapter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )
    writing_run_id: Mapped[int] = mapped_column(
        ForeignKey("writing_runs.id"), nullable=False, index=True
    )
    based_on_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("draft_versions.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(nullable=False, default="draft")
    revision_sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    acceptance_override_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
