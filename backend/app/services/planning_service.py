"""规划业务逻辑。"""

import logging
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound, AppException
from app.models.novel import Novel
from app.models.planning import VolumeArc, PlanVersion, ReviewIssue
from app.models.foreshadowing import Foreshadowing
from app.models.writing import NovelBlueprint, ChapterPlan
from app.repositories.planning_repo import VolumeArcRepo, PlanVersionRepo
from app.repositories.writing_repo import BlueprintRepo, ChapterPlanRepo

logger = logging.getLogger("novel_agent.planning")


class PlanningService:
    def __init__(self, db: AsyncSession, user_id: int, novel_id: int):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.arc_repo = VolumeArcRepo(db)
        self.version_repo = PlanVersionRepo(db)
        self.blueprint_repo = BlueprintRepo(db)
        self.plan_repo = ChapterPlanRepo(db)

    async def _ensure_owned_novel(self) -> Novel:
        result = await self.db.execute(
            select(Novel).where(Novel.id == self.novel_id)
        )
        novel = result.scalar_one_or_none()
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != self.user_id:
            raise NotFound("小说不存在")
        return novel

    # ── Volume Arcs ────────────────────────────────────────────────────────

    async def create_volume_arc(self, data: dict) -> VolumeArc:
        await self._ensure_owned_novel()
        arc = await self.arc_repo.create(self.novel_id, data)
        await self.db.commit()
        return arc

    async def list_volume_arcs(self) -> list[VolumeArc]:
        await self._ensure_owned_novel()
        return await self.arc_repo.list_by_novel(self.novel_id)

    async def get_volume_arc(self, arc_id: int) -> VolumeArc:
        await self._ensure_owned_novel()
        arc = await self.arc_repo.get_by_id(arc_id)
        if not arc or arc.novel_id != self.novel_id:
            raise NotFound("卷弧不存在")
        return arc

    async def update_volume_arc(self, arc_id: int, data: dict) -> VolumeArc:
        await self._ensure_owned_novel()
        arc = await self.arc_repo.get_by_id(arc_id)
        if not arc or arc.novel_id != self.novel_id:
            raise NotFound("卷弧不存在")
        # Create a PlanVersion snapshot before updating
        snapshot = {
            "title": arc.title,
            "goal": arc.goal,
            "start_state": arc.start_state,
            "end_state": arc.end_state,
            "key_events": arc.key_events,
            "pacing_notes": arc.pacing_notes,
            "foreshadowing_plan": arc.foreshadowing_plan,
            "order_index": arc.order_index,
            "status": arc.status,
        }
        current_version = await self.version_repo.get_current("volume_arc", arc_id)
        next_version = (current_version.version + 1) if current_version else 1
        await self.version_repo.create(self.novel_id, {
            "plan_type": "volume_arc",
            "plan_id": arc_id,
            "version": next_version,
            "change_reason": data.get("change_reason", "更新卷弧"),
            "impact_scope": data.get("impact_scope", ""),
            "snapshot_json": snapshot,
            "status": "current",
        })
        result = await self.arc_repo.update(arc, data)
        await self.db.commit()
        return result

    async def activate_volume_arc(self, arc_id: int) -> VolumeArc:
        await self._ensure_owned_novel()
        arc = await self.arc_repo.get_by_id(arc_id)
        if not arc or arc.novel_id != self.novel_id:
            raise NotFound("卷弧不存在")
        if arc.status == "archived":
            raise AppException("已归档的卷弧无法激活")
        await self.arc_repo.deactivate_all(self.novel_id)
        result = await self.arc_repo.update(arc, {"status": "active"})
        await self.db.commit()
        return result

    # ── Plan Versions ──────────────────────────────────────────────────────

    async def create_plan_version(self, data: dict) -> PlanVersion:
        await self._ensure_owned_novel()
        plan_type = data["plan_type"]
        plan_id = data["plan_id"]
        # Archive previous current version
        await self.version_repo.archive_all(plan_type, plan_id)
        # Determine next version number
        current = await self.version_repo.get_current(plan_type, plan_id)
        next_version = (current.version + 1) if current else 1
        version = await self.version_repo.create(self.novel_id, {
            "plan_type": plan_type,
            "plan_id": plan_id,
            "version": next_version,
            "change_reason": data.get("change_reason", ""),
            "impact_scope": data.get("impact_scope", ""),
            "snapshot_json": data.get("snapshot_json", {}),
            "status": "current",
        })
        await self.db.commit()
        return version

    async def list_plan_versions(self, plan_type: str, plan_id: int) -> list[PlanVersion]:
        await self._ensure_owned_novel()
        return await self.version_repo.list_by_entity(plan_type, plan_id)

    async def activate_plan_version(self, version_id: int) -> PlanVersion:
        await self._ensure_owned_novel()
        version = await self.version_repo.get_by_id(version_id)
        if not version or version.novel_id != self.novel_id:
            raise NotFound("计划版本不存在")
        if version.status == "archived":
            raise AppException("已归档的计划版本无法直接激活，请创建新版本")
        # Archive all other current versions for this entity
        await self.version_repo.archive_all(version.plan_type, version.plan_id)
        result = await self.version_repo.update_status(version, "current")
        await self.db.commit()
        return result

    # ── Dashboard ──────────────────────────────────────────────────────────

    async def get_planning_dashboard(self) -> dict[str, Any]:
        await self._ensure_owned_novel()

        active_blueprint = await self.blueprint_repo.get_active(self.novel_id)
        active_volume_arcs = await self.arc_repo.list_by_novel(self.novel_id)
        active_volume_arcs = [a for a in active_volume_arcs if a.status == "active"]

        # Current chapter plans: latest or active chapter plans
        result = await self.db.execute(
            select(ChapterPlan)
            .where(
                ChapterPlan.novel_id == self.novel_id,
                ChapterPlan.status == "ready",
            )
            .order_by(ChapterPlan.position.asc())
        )
        current_chapter_plans = list(result.scalars().all())

        # Open review issues
        result = await self.db.execute(
            select(ReviewIssue).where(
                ReviewIssue.novel_id == self.novel_id,
                ReviewIssue.status == "open",
            )
        )
        open_review_issues = list(result.scalars().all())

        # Unresolved foreshadowings
        result = await self.db.execute(
            select(Foreshadowing).where(
                Foreshadowing.novel_id == self.novel_id,
                Foreshadowing.status.in_(["planted", "developing"]),
            )
        )
        unresolved_foreshadowings = list(result.scalars().all())

        def _to_dict(obj, exclude=None):
            if obj is None:
                return None
            exclude = exclude or set()
            from sqlalchemy.inspection import inspect as sa_inspect
            mapper = sa_inspect(obj.__class__)
            return {
                c.key: getattr(obj, c.key)
                for c in mapper.column_attrs
                if c.key not in exclude
            }

        return {
            "active_blueprint": _to_dict(active_blueprint),
            "active_volume_arcs": [_to_dict(a) for a in active_volume_arcs],
            "current_chapter_plans": [_to_dict(p) for p in current_chapter_plans],
            "open_review_issues": [_to_dict(i) for i in open_review_issues],
            "unresolved_foreshadowings": [_to_dict(f) for f in unresolved_foreshadowings],
        }
