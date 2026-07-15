"""Phase 6 Author Studio — WritingSession lifecycle service.

Provides session creation, retrieval, listing, run-to-session binding,
message listing, source projection, and workspace serialization.
Ownership checks follow the same pattern as DraftVersionService.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.novel import Novel
from app.models.writing import WritingRun
from app.models.writing_session import DraftWorkingCopy, WritingMessage, WritingSession
from app.repositories.writing_repo import WritingRunRepo
from app.repositories.writing_session_repo import WritingSessionRepo
from app.schemas.writing_studio import (
    DraftWorkingCopyOut,
    StudioSourceOut,
    WritingMessageOut,
    WritingSessionOut,
)


class WritingSessionService:
    def __init__(self, db: AsyncSession, user_id: int, novel_id: int):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.repo = WritingSessionRepo(db)
        self.run_repo = WritingRunRepo(db)

    # ── Private helpers ──────────────────────────────────────────────

    async def _ensure_owned_novel(self) -> Novel:
        novel = await self.db.get(Novel, self.novel_id)
        if novel is None or novel.user_id != self.user_id:
            raise NotFound("小说不存在")
        return novel

    async def _get_owned_run(self, run_id: int) -> WritingRun:
        await self._ensure_owned_novel()
        run = await self.run_repo.get_by_id(run_id)
        if run is None or run.novel_id != self.novel_id:
            raise NotFound("写作运行不存在")
        return run

    # ── Public API ───────────────────────────────────────────────────

    async def create_session(
        self, target_chapter_id: int | None, title: str
    ) -> WritingSession:
        await self._ensure_owned_novel()
        session = await self.repo.create(
            self.novel_id,
            {
                "target_chapter_id": target_chapter_id,
                "title": title,
                "status": "active",
            },
        )
        await self.db.commit()
        return session

    async def get_session(self, session_id: int) -> WritingSession:
        session = await self.repo.get(session_id, self.novel_id)
        if session is None:
            raise NotFound("创作会话不存在")
        return session

    async def list_sessions(self) -> list[WritingSession]:
        await self._ensure_owned_novel()
        return await self.repo.list_by_novel(self.novel_id)

    async def get_or_create_for_run(self, run_id: int) -> WritingSession:
        run = await self._get_owned_run(run_id)
        existing = await self.repo.get_by_run(self.novel_id, run.id)
        if existing is not None:
            return existing
        session = await self.repo.create(
            self.novel_id,
            {
                "target_chapter_id": run.target_chapter_id,
                "active_writing_run_id": run.id,
                "title": f"草稿 {run.id}",
                "status": "active",
            },
        )
        run.writing_session_id = session.id
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def list_messages(self, session_id: int) -> list[WritingMessage]:
        await self.get_session(session_id)
        return await self.repo.list_messages(session_id)

    async def get_sources(self, run_id: int) -> list[StudioSourceOut]:
        run = await self._get_owned_run(run_id)
        items = run.context_snapshot_json.get("source_items", [])
        return [StudioSourceOut.model_validate(item) for item in items]

    async def to_workspace_out(self, session: WritingSession) -> dict:
        messages = await self.repo.list_messages(session.id)
        working_copy = None
        if session.active_writing_run_id is not None:
            working_copy = await self.db.get(
                DraftWorkingCopy, session.active_writing_run_id
            )
        return {
            "session": WritingSessionOut.model_validate(session).model_dump(),
            "messages": [
                WritingMessageOut.model_validate(item).model_dump()
                for item in messages
            ],
            "working_copy": (
                DraftWorkingCopyOut.model_validate(working_copy).model_dump()
                if working_copy
                else None
            ),
        }
