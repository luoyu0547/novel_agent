"""Phase 6 Author Studio — WorkingCopy autosave and atomic revision flush.

Manages the DraftWorkingCopy buffer: save() persists author edits to the
working copy row, flush() atomically promotes changed content into a
manual-edit DraftRevision on the current DraftVersion.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, NotFound
from app.models.novel import Novel
from app.models.writing import WritingRun
from app.models.writing_session import DraftWorkingCopy
from app.repositories.draft_version_repo import DraftVersionRepo
from app.repositories.writing_session_repo import WritingSessionRepo
from app.services.draft_version_service import DraftVersionService


class WorkingCopyService:
    """WorkingCopy autosave and flush service.

    - save(): persists title/content to the DraftWorkingCopy row with
      optimistic concurrency via base_revision_sequence.
    - flush(): if the working copy content differs from the current
      DraftVersion, calls DraftVersionService.save_manual_revision() to
      create an applied manual-edit revision, then updates the working
      copy pointers.
    """

    def __init__(self, db: AsyncSession, user_id: int, novel_id: int):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.repo = WritingSessionRepo(db)
        self.version_repo = DraftVersionRepo(db)
        self.version_service = DraftVersionService(db, user_id, novel_id)

    # ── Private helpers ──────────────────────────────────────────────

    async def _ensure_owned_novel(self) -> Novel:
        novel = await self.db.get(Novel, self.novel_id)
        if novel is None or novel.user_id != self.user_id:
            raise NotFound("小说不存在")
        return novel

    async def _get_owned_mutable_run(self, run_id: int) -> WritingRun:
        """Get run, verify ownership, and ensure it is still mutable."""
        await self._ensure_owned_novel()
        result = await self.db.execute(
            select(WritingRun).where(
                WritingRun.id == run_id,
                WritingRun.novel_id == self.novel_id,
            )
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFound("写作运行不存在")
        if run.status in ("accepted", "discarded"):
            raise BadRequest("写作运行已接受或丢弃，不可编辑")
        return run

    async def _get_owned_copy(self, run_id: int) -> DraftWorkingCopy:
        """Get the working copy for a run, raising if not found."""
        await self._get_owned_mutable_run(run_id)
        copy = await self.db.get(DraftWorkingCopy, run_id)
        if copy is None:
            raise NotFound("工作副本不存在")
        return copy

    # ── Public API ───────────────────────────────────────────────────

    async def save(
        self,
        run_id: int,
        title: str,
        content: str,
        base_revision_sequence: int,
    ) -> DraftWorkingCopy:
        """Persist author edits to the working copy row.

        Validates that base_revision_sequence matches the current
        DraftVersion's revision_sequence to detect stale edits.
        """
        run = await self._get_owned_mutable_run(run_id)
        version = await self.version_repo.get_current(run.id)
        if version is None or version.revision_sequence != base_revision_sequence:
            raise BadRequest("基础修订序列已过期，请刷新后重试")
        return await self.repo.upsert_working_copy(
            run.id,
            {
                "draft_version_id": version.id,
                "title": title,
                "content": content,
                "base_revision_sequence": base_revision_sequence,
            },
        )

    async def flush(
        self, run_id: int, reason: str = "作者工作副本保存"
    ) -> "DraftVersion":
        """Atomically promote working copy content into a manual revision.

        If the working copy content matches the current version, this is a
        no-op that returns the current version. Otherwise, calls
        DraftVersionService.save_manual_revision() to create an applied
        manual-edit DraftRevision, then updates the working copy's
        draft_version_id and base_revision_sequence pointers.
        """
        copy = await self._get_owned_copy(run_id)
        version = await self.version_repo.get_current(run_id)
        if version is None:
            raise BadRequest("当前没有可编辑的草稿版本")
        if copy.content == version.content:
            return version
        version, _ = await self.version_service.save_manual_revision(
            run_id, copy.content, reason, copy.base_revision_sequence,
        )
        copy.draft_version_id = version.id
        copy.base_revision_sequence = version.revision_sequence
        await self.db.commit()
        return version
