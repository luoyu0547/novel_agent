"""Repository for WritingSession, WritingMessage, DraftWorkingCopy."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.writing_session import DraftWorkingCopy, WritingMessage, WritingSession


class WritingSessionRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int) -> list[WritingSession]:
        result = await self.db.execute(
            select(WritingSession)
            .where(WritingSession.novel_id == novel_id)
            .order_by(WritingSession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, session_id: int, novel_id: int) -> WritingSession | None:
        result = await self.db.execute(
            select(WritingSession).where(
                WritingSession.id == session_id,
                WritingSession.novel_id == novel_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_run(self, novel_id: int, run_id: int) -> WritingSession | None:
        result = await self.db.execute(
            select(WritingSession).where(
                WritingSession.novel_id == novel_id,
                WritingSession.active_writing_run_id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, novel_id: int, data: dict) -> WritingSession:
        session = WritingSession(novel_id=novel_id, **data)
        self.db.add(session)
        await self.db.flush()
        return session

    async def list_messages(self, session_id: int) -> list[WritingMessage]:
        result = await self.db.execute(
            select(WritingMessage)
            .where(WritingMessage.session_id == session_id)
            .order_by(WritingMessage.created_at.asc(), WritingMessage.id.asc())
        )
        return list(result.scalars().all())

    async def get_by_idempotency_key(self, key: str) -> WritingMessage | None:
        result = await self.db.execute(
            select(WritingMessage).where(WritingMessage.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def upsert_working_copy(self, run_id: int, data: dict) -> DraftWorkingCopy:
        copy = await self.db.get(DraftWorkingCopy, run_id)
        if copy is None:
            copy = DraftWorkingCopy(writing_run_id=run_id, **data)
            self.db.add(copy)
        else:
            for key, value in data.items():
                setattr(copy, key, value)
        await self.db.flush()
        return copy
