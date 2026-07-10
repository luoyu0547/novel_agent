"""上下文快照构建器。为 AI 写作提供完整的小说状态快照。"""

import datetime
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFound
from app.models.foreshadowing import Foreshadowing
from app.models.novel import Novel
from app.models.plot_fact import PlotFact
from app.models.writing import ChapterBrief, ChapterPlan
from app.repositories.plot_planning_repo import PlotPlanningRepo

logger = logging.getLogger("novel_agent.context_package")


class ContextPackageService:
    def __init__(self, db: AsyncSession, user_id: int, novel_id: int):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.repo = PlotPlanningRepo(db)

    async def _ensure_owned_novel(self) -> Novel:
        result = await self.db.execute(
            select(Novel)
            .where(Novel.id == self.novel_id)
            .options(
                selectinload(Novel.chapters),
                selectinload(Novel.characters),
                selectinload(Novel.world_settings),
                selectinload(Novel.author_foundation),
            )
        )
        novel = result.scalar_one_or_none()
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != self.user_id:
            raise NotFound("小说不存在")
        return novel

    async def build_for_brief(
        self,
        brief_id: int,
        plot_plan_revision_id: int,
        author_input: str = "",
    ) -> dict:
        novel = await self._ensure_owned_novel()

        brief = await self.db.get(ChapterBrief, brief_id)
        if not brief or brief.novel_id != self.novel_id:
            raise NotFound("章节任务书不存在")

        chapter_plan = await self.db.get(ChapterPlan, brief.chapter_plan_id)
        if not chapter_plan or chapter_plan.novel_id != self.novel_id:
            raise NotFound("章节计划不存在")

        plan_revision = await self.repo.get_plan_revision(plot_plan_revision_id, self.novel_id)
        if not plan_revision:
            raise NotFound("剧情计划修订不存在")

        plot_unit = await self.repo.get_plot_unit(plan_revision.plot_unit_id, self.novel_id)

        foundation = await self.repo.get_foundation(self.novel_id)
        latest_revision = await self.repo.get_latest_foundation_revision(self.novel_id)

        locked_chapters = [c for c in novel.chapters if c.status == "locked"]

        characters = []
        if novel.characters:
            characters = [
                {
                    "id": c.id,
                    "name": c.name,
                    "story_role": c.story_role,
                    "identity": c.identity,
                    "personality": c.personality,
                    "current_state": c.current_state,
                }
                for c in novel.characters
            ]

        world_settings = []
        if novel.world_settings:
            world_settings = [
                {"id": ws.id, "title": ws.title, "category": ws.category, "content": ws.content}
                for ws in novel.world_settings
            ]

        plot_facts_result = await self.db.execute(
            select(PlotFact).where(PlotFact.novel_id == self.novel_id)
        )
        plot_facts = [
            {"id": pf.id, "fact_type": pf.fact_type, "content": pf.content, "importance": pf.importance}
            for pf in plot_facts_result.scalars().all()
        ]

        foreshadowings_result = await self.db.execute(
            select(Foreshadowing).where(Foreshadowing.novel_id == self.novel_id)
        )
        foreshadowings = [
            {
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "hidden_truth": f.hidden_truth,
                "status": f.status,
                "risk_warning": f.risk_warning,
            }
            for f in foreshadowings_result.scalars().all()
        ]

        foundation_data = {}
        if foundation:
            foundation_data = {
                "outline": foundation.outline,
                "current_intent": foundation.current_intent,
                "stage_goal": foundation.stage_goal,
                "constraints_json": foundation.constraints_json,
                "version": foundation.version,
            }

        plot_unit_data = {}
        if plot_unit:
            plot_unit_data = {
                "id": plot_unit.id,
                "title": plot_unit.title,
                "scope_type": plot_unit.scope_type,
                "start_position": plot_unit.start_position,
                "end_position": plot_unit.end_position,
                "author_goal": plot_unit.author_goal,
                "start_state": plot_unit.start_state,
                "end_state": plot_unit.end_state,
            }

        return {
            "author_foundation": foundation_data,
            "published_canon": {
                "chapters": [
                    {
                        "id": c.id,
                        "title": c.title,
                        "content": c.content,
                        "summary": c.summary,
                    }
                    for c in locked_chapters
                ],
            },
            "plot_unit": plot_unit_data,
            "plot_plan": plan_revision.plan_json,
            "chapter_brief": brief.brief_json,
            "chapter_plan": chapter_plan.content_json if chapter_plan else {},
            "characters": characters,
            "world_settings": world_settings,
            "plot_facts": plot_facts,
            "foreshadowings": foreshadowings,
            "style_guide": novel.style_guide or "",
            "author_input": author_input,
            "snapshot": {
                "foundation_revision_id": latest_revision.id if latest_revision else None,
                "plot_plan_revision_id": plot_plan_revision_id,
                "published_chapter_ids": [c.id for c in locked_chapters],
                "chapter_brief_id": brief_id,
                "generated_at": datetime.datetime.now().isoformat(),
            },
        }
