"""Phase 4 辅助修订——DraftVersion 仓储层。

DraftVersionRepo 管理 DraftVersion 及其关联 DraftRevision 的查询。
所有 get/list 方法包含 novel_id 归属过滤。"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.draft_version import DraftVersion
from app.models.plot_planning import DraftRevision


class DraftVersionRepo:
    """DraftVersion 仓储，提供版本快照的 CRUD 及修订关联查询。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, version_id: int, novel_id: int) -> Optional[DraftVersion]:
        result = await self.db.execute(
            select(DraftVersion).where(
                DraftVersion.id == version_id,
                DraftVersion.novel_id == novel_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_current(self, writing_run_id: int) -> Optional[DraftVersion]:
        """返回 writing_run 当前 draft 状态的版本。"""
        result = await self.db.execute(
            select(DraftVersion).where(
                DraftVersion.writing_run_id == writing_run_id,
                DraftVersion.status == "draft",
            )
        )
        return result.scalar_one_or_none()

    async def list_by_run(self, writing_run_id: int) -> list[DraftVersion]:
        """列出 writing_run 的所有版本，version DESC。"""
        result = await self.db.execute(
            select(DraftVersion)
            .where(DraftVersion.writing_run_id == writing_run_id)
            .order_by(DraftVersion.version.desc())
        )
        return list(result.scalars().all())

    async def next_version_number(self, writing_run_id: int) -> int:
        """返回下一个可用的版本号（当前最大 version + 1）。"""
        result = await self.db.execute(
            select(func.coalesce(func.max(DraftVersion.version), 0)).where(
                DraftVersion.writing_run_id == writing_run_id
            )
        )
        max_version = result.scalar()
        return (max_version or 0) + 1

    async def create(self, novel_id: int, data: dict) -> DraftVersion:
        version = DraftVersion(novel_id=novel_id, **data)
        self.db.add(version)
        await self.db.flush()
        return version

    async def update(self, version: DraftVersion, data: dict) -> DraftVersion:
        for key, value in data.items():
            setattr(version, key, value)
        await self.db.flush()
        return version

    async def list_revisions(self, draft_version_id: int) -> list[DraftRevision]:
        """列出指定 DraftVersion 下的所有修订，按 created_at DESC, id DESC。"""
        result = await self.db.execute(
            select(DraftRevision)
            .where(DraftRevision.draft_version_id == draft_version_id)
            .order_by(DraftRevision.created_at.desc(), DraftRevision.id.desc())
        )
        return list(result.scalars().all())

    async def get_revision(
        self, revision_id: int, novel_id: int
    ) -> Optional[DraftRevision]:
        result = await self.db.execute(
            select(DraftRevision).where(
                DraftRevision.id == revision_id,
                DraftRevision.novel_id == novel_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_revision(self, novel_id: int, data: dict) -> DraftRevision:
        revision = DraftRevision(novel_id=novel_id, **data)
        self.db.add(revision)
        await self.db.flush()
        return revision

    async def list_sibling_candidates(
        self,
        draft_version_id: int,
        base_revision_sequence: int,
        base_content_hash: str,
    ) -> list[DraftRevision]:
        """查找同版本、同基础序列、同哈希的候选修订（并发检测）。"""
        result = await self.db.execute(
            select(DraftRevision).where(
                DraftRevision.draft_version_id == draft_version_id,
                DraftRevision.base_revision_sequence == base_revision_sequence,
                DraftRevision.base_content_hash == base_content_hash,
                DraftRevision.status == "candidate",
            )
        )
        return list(result.scalars().all())
