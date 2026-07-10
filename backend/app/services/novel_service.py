"""小说和章节的业务逻辑。所有操作通过 user_id 所有权守卫确保数据隔离。"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, Forbidden, NotFound
from app.repositories.novel_repo import ChapterRepo, NovelRepo


class NovelService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = NovelRepo(db)
        self.chapter_repo = ChapterRepo(db)

    async def create(self, user_id: int, title: str, description: Optional[str] = None, genre: Optional[str] = None, style_guide: Optional[str] = None):
        return await self.repo.create(user_id, title, description, genre, style_guide)

    async def list(self, user_id: int):
        return await self.repo.list_by_user(user_id)

    async def get(self, novel_id: int, user_id: int):
        """获取小说。找不到或不属于当前用户时均抛出 NotFound（避免泄露小说是否存在）。"""
        novel = await self.repo.get_by_id(novel_id)
        if not novel or novel.user_id != user_id:
            raise NotFound("小说不存在")
        return novel

    async def update(self, user_id: int, novel_id: int, title: Optional[str], description: Optional[str], genre: Optional[str], style_guide: Optional[str]):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise Forbidden("无权修改该小说")
        return await self.repo.update(novel, title, description, genre, style_guide)

    async def delete(self, user_id: int, novel_id: int):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise Forbidden("无权删除该小说")
        await self.repo.delete(novel)

    async def create_chapter(self, user_id: int, novel_id: int, title: str, content: str = "", summary: str = "", status: str = "draft"):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise Forbidden("无权在该小说下创建章节")
        return await self.chapter_repo.create(novel_id, title, content, summary, status)

    async def get_chapter(self, novel_id: int, chapter_id: int, user_id: int):
        novel = await self.repo.get_by_id(novel_id)
        if not novel or novel.user_id != user_id:
            raise NotFound("小说不存在")
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter or chapter.novel_id != novel_id:
            raise NotFound("章节不存在")
        return chapter

    async def update_chapter(self, user_id: int, novel_id: int, chapter_id: int, title: Optional[str], content: Optional[str], summary: Optional[str], status: Optional[str]):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise Forbidden("无权修改该章节")
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter or chapter.novel_id != novel_id:
            raise NotFound("章节不存在")
        return await self.chapter_repo.update(chapter, title, content, summary, status)

    async def delete_chapter(self, user_id: int, novel_id: int, chapter_id: int):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise Forbidden("无权删除该章节")
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter or chapter.novel_id != novel_id:
            raise NotFound("章节不存在")
        await self.chapter_repo.delete(chapter)

    async def publish_chapter(self, user_id: int, novel_id: int, chapter_id: int):
        novel = await self.repo.get_by_id(novel_id)
        if not novel or novel.user_id != user_id:
            raise NotFound("小说不存在")
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter or chapter.novel_id != novel_id:
            raise NotFound("章节不存在")
        if chapter.status == "locked":
            raise AppException("该章节已发布")

        from app.repositories.plot_planning_repo import PlotPlanningRepo
        pp_repo = PlotPlanningRepo(self.db)
        pending = await pp_repo.list_pending_decisions(novel_id)
        if pending:
            raise AppException(f"存在 {len(pending)} 个待处理决策，请先解决")

        from app.repositories.writing_repo import WritingRunRepo
        run_repo = WritingRunRepo(self.db)
        runs = await run_repo.list_by_novel(novel_id)
        blocked = [r for r in runs if r.planning_blocked]
        if blocked:
            raise AppException("存在规划阻塞的写作运行")

        chapter.status = "locked"
        await self.db.commit()
        await self.db.refresh(chapter)
        return chapter
