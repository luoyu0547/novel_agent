"""剧情规划业务逻辑。"""

import datetime
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.plot_planning import ConflictOutput
from app.ai.writer import BaseWritingGenerator, FakePhase3WritingGenerator
from app.core.exceptions import BadRequest, NotFound
from app.models.novel import Novel
from app.models.plot_planning import (
    AuthorFoundation,
    AuthorFoundationRevision,
    PlanningDecision,
    PlotPlanRevision,
    PlotUnit,
)
from app.repositories.plot_planning_repo import PlotPlanningRepo

logger = logging.getLogger("novel_agent.plot_planning")

VALID_SOURCES = {"during_generation", "during_review"}


class PlotPlanningService:
    def __init__(
        self,
        db: AsyncSession,
        user_id: int,
        novel_id: int,
        generator: Optional[BaseWritingGenerator] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.generator = generator or FakePhase3WritingGenerator()
        self.repo = PlotPlanningRepo(db)

    async def _ensure_owned_novel(self) -> Novel:
        result = await self.db.execute(
            select(Novel)
            .where(Novel.id == self.novel_id)
            .options(
                selectinload(Novel.chapters),
                selectinload(Novel.characters),
                selectinload(Novel.world_settings),
                selectinload(Novel.plot_units),
                selectinload(Novel.author_foundation),
            )
        )
        novel = result.scalar_one_or_none()
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != self.user_id:
            raise NotFound("小说不存在")
        return novel

    async def get_foundation(self) -> AuthorFoundation:
        await self._ensure_owned_novel()
        foundation = await self.repo.get_foundation(self.novel_id)
        if not foundation:
            raise NotFound("作者资料不存在")
        return foundation

    async def update_foundation(self, data: dict, change_reason: str) -> AuthorFoundation:
        await self._ensure_owned_novel()
        foundation = await self.repo.get_foundation(self.novel_id)
        if not foundation:
            foundation = await self.repo.create_foundation(self.novel_id, {
                "outline": data.get("outline", ""),
                "current_intent": data.get("current_intent", ""),
                "stage_goal": data.get("stage_goal", ""),
                "constraints_json": data.get("constraints_json", {}),
                "version": 1,
            })
        else:
            foundation.version += 1

        for key in ("outline", "current_intent", "stage_goal", "constraints_json"):
            if key in data:
                setattr(foundation, key, data[key])

        foundation.updated_at = datetime.datetime.now()

        await self.repo.create_foundation_revision(self.novel_id, {
            "foundation_id": foundation.id,
            "version": foundation.version,
            "snapshot_json": {
                "outline": foundation.outline,
                "current_intent": foundation.current_intent,
                "stage_goal": foundation.stage_goal,
                "constraints_json": foundation.constraints_json,
            },
            "change_reason": change_reason,
        })

        await self.repo.mark_plans_stale(self.novel_id)
        await self.db.commit()
        await self.db.refresh(foundation)
        return foundation

    async def list_foundation_revisions(self) -> list[AuthorFoundationRevision]:
        await self._ensure_owned_novel()
        return await self.repo.list_foundation_revisions(self.novel_id)

    async def create_plot_unit(self, data: dict) -> PlotUnit:
        await self._ensure_owned_novel()
        revision = await self.repo.get_latest_foundation_revision(self.novel_id)
        if not revision:
            raise BadRequest("请先设置作者资料")
        unit_data = {**data, "foundation_revision_id": revision.id}
        unit = await self.repo.create_plot_unit(self.novel_id, unit_data)
        await self.db.commit()
        await self.db.refresh(unit)
        return unit

    async def list_plot_units(self) -> list[PlotUnit]:
        await self._ensure_owned_novel()
        return await self.repo.list_plot_units(self.novel_id)

    async def get_plot_unit(self, unit_id: int) -> PlotUnit:
        await self._ensure_owned_novel()
        unit = await self.repo.get_plot_unit(unit_id, self.novel_id)
        if not unit:
            raise NotFound("剧情单元不存在")
        return unit

    async def generate_plan(self, plot_unit_id: int, author_input: str = "") -> PlotPlanRevision:
        novel = await self._ensure_owned_novel()
        unit = await self.repo.get_plot_unit(plot_unit_id, self.novel_id)
        if not unit:
            raise NotFound("剧情单元不存在")

        foundation = await self.repo.get_foundation(self.novel_id)
        if not foundation:
            raise BadRequest("请先设置作者资料")
        latest_revision = await self.repo.get_latest_foundation_revision(self.novel_id)
        if not latest_revision:
            raise BadRequest("请先设置作者资料")

        foundation_data = {
            "outline": foundation.outline,
            "current_intent": foundation.current_intent,
            "stage_goal": foundation.stage_goal,
            "constraints_json": foundation.constraints_json,
        }
        plot_unit_data = {
            "title": unit.title,
            "scope_type": unit.scope_type,
            "start_position": unit.start_position,
            "end_position": unit.end_position,
            "author_goal": unit.author_goal,
            "start_state": unit.start_state,
            "end_state": unit.end_state,
        }
        locked_chapters = [c for c in novel.chapters if c.status == "locked"]
        published_canon = {
            "chapters": [
                {"id": c.id, "title": c.title, "content": c.content, "summary": c.summary}
                for c in locked_chapters
            ]
        }

        try:
            plan_output = await self.generator.generate_plot_plan(foundation_data, plot_unit_data, published_canon)
        except Exception as e:
            await self.db.rollback()
            raise

        if not isinstance(plan_output, dict):
            await self.db.rollback()
            raise BadRequest("生成器返回无效数据")

        existing = await self.repo.list_plan_revisions(plot_unit_id)
        version = (existing[0].version if existing else 0) + 1

        based_on_chapter_id = locked_chapters[-1].id if locked_chapters else None

        plan = await self.repo.create_plan_revision(self.novel_id, {
            "plot_unit_id": plot_unit_id,
            "foundation_revision_id": latest_revision.id,
            "based_on_published_chapter_id": based_on_chapter_id,
            "version": version,
            "plan_json": plan_output,
            "change_reason": "plan_generation",
            "status": "draft",
        })
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def list_plan_revisions(self, plot_unit_id: int) -> list[PlotPlanRevision]:
        await self._ensure_owned_novel()
        unit = await self.repo.get_plot_unit(plot_unit_id, self.novel_id)
        if not unit:
            raise NotFound("剧情单元不存在")
        return await self.repo.list_plan_revisions(plot_unit_id)

    async def confirm_plan(self, plot_unit_id: int, revision_id: int) -> PlotPlanRevision:
        await self._ensure_owned_novel()
        unit = await self.repo.get_plot_unit(plot_unit_id, self.novel_id)
        if not unit:
            raise NotFound("剧情单元不存在")
        revision = await self.repo.get_plan_revision(revision_id, self.novel_id)
        if not revision:
            raise NotFound("剧情计划修订不存在")
        if revision.plot_unit_id != plot_unit_id:
            raise BadRequest("修订不属于该剧情单元")
        if revision.status != "draft":
            raise BadRequest("只能确认草稿状态的计划")
        await self.repo.archive_active_plans(plot_unit_id)
        revision.status = "active"
        await self.db.commit()
        await self.db.refresh(revision)
        return revision

    async def create_decision_from_conflict(
        self,
        conflict: ConflictOutput,
        source: str,
        run_id: int,
    ) -> PlanningDecision:
        if source not in VALID_SOURCES:
            raise BadRequest(f"无效的 source 值: {source}")
        if len(conflict.options) < 2:
            raise BadRequest("决策方案少于 2 个")

        await self._ensure_owned_novel()
        from app.repositories.writing_repo import WritingRunRepo
        run_repo = WritingRunRepo(self.db)
        run = await run_repo.get_by_id(run_id)
        snapshot = run.context_snapshot_json or {} if run else {}
        plot_plan_revision_id = snapshot.get("plot_plan_revision_id")
        plot_unit_id = None
        if plot_plan_revision_id:
            plan_revision = await self.repo.get_plan_revision(plot_plan_revision_id, self.novel_id)
            if plan_revision:
                plot_unit_id = plan_revision.plot_unit_id
                plan_revision.status = "blocked"
        decision = await self.repo.create_decision(self.novel_id, {
            "plot_unit_id": plot_unit_id,
            "plot_plan_revision_id": plot_plan_revision_id,
            "writing_run_id": run_id,
            "source": source,
            "status": "pending",
            "conflict_summary": conflict.core_conflict,
            "evidence_json": conflict.evidence or {},
            "options_json": [
                {"label": o.label, "action": o.action, "consequence": o.consequence}
                for o in conflict.options
            ],
            "recommended_index": conflict.recommended_index,
            "recommendation_reason": conflict.recommendation_reason,
            "impact_scope_json": conflict.impact_scope,
        })
        return decision

    async def list_pending_decisions(self) -> list[PlanningDecision]:
        await self._ensure_owned_novel()
        return await self.repo.list_pending_decisions(self.novel_id)

    async def list_decisions(self, status: Optional[str] = None) -> list[PlanningDecision]:
        await self._ensure_owned_novel()
        return await self.repo.list_decisions(self.novel_id, status)

    async def get_decision(self, decision_id: int) -> PlanningDecision:
        await self._ensure_owned_novel()
        decision = await self.repo.get_decision(decision_id, self.novel_id)
        if not decision:
            raise NotFound("决策不存在")
        return decision
