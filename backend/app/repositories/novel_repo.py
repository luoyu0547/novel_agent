from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.novel import Chapter, Novel


class NovelRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, title: str, description: Optional[str] = None) -> Novel:
        novel = Novel(user_id=user_id, title=title, description=description)
        self.db.add(novel)
        await self.db.commit()
        await self.db.refresh(novel)
        return novel

    async def list_by_user(self, user_id: int) -> list[Novel]:
        result = await self.db.execute(
            select(Novel).where(Novel.user_id == user_id).order_by(Novel.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, novel_id: int) -> Optional[Novel]:
        result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id).options(selectinload(Novel.chapters))
        )
        return result.scalar_one_or_none()

    async def update(self, novel: Novel, title: Optional[str], description: Optional[str]) -> Novel:
        if title is not None:
            novel.title = title
        if description is not None:
            novel.description = description
        await self.db.commit()
        await self.db.refresh(novel)
        return novel

    async def delete(self, novel: Novel) -> None:
        await self.db.delete(novel)
        await self.db.commit()


class ChapterRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, novel_id: int, title: str, content: str = "") -> Chapter:
        chapter = Chapter(novel_id=novel_id, title=title, content=content)
        self.db.add(chapter)
        await self.db.commit()
        await self.db.refresh(chapter)
        return chapter

    async def get_by_id(self, chapter_id: int) -> Optional[Chapter]:
        return await self.db.get(Chapter, chapter_id)

    async def update(self, chapter: Chapter, title: Optional[str], content: Optional[str]) -> Chapter:
        if title is not None:
            chapter.title = title
        if content is not None:
            chapter.content = content
        await self.db.commit()
        await self.db.refresh(chapter)
        return chapter

    async def delete(self, chapter: Chapter) -> None:
        await self.db.delete(chapter)
        await self.db.commit()
