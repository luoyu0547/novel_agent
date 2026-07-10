from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plot_planning import (
    AuthorFoundation,
    AuthorFoundationRevision,
    DraftRevision,
    PlanningDecision,
    PlotPlanRevision,
    PlotUnit,
)


class PlotPlanningRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_foundation(self, novel_id: int) -> Optional[AuthorFoundation]:
        result = await self.db.execute(
            select(AuthorFoundation).where(AuthorFoundation.novel_id == novel_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_foundation_revision(self, novel_id: int) -> Optional[AuthorFoundationRevision]:
        result = await self.db.execute(
            select(AuthorFoundationRevision)
            .where(AuthorFoundationRevision.novel_id == novel_id)
            .order_by(AuthorFoundationRevision.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_foundation_revisions(self, novel_id: int) -> list[AuthorFoundationRevision]:
        result = await self.db.execute(
            select(AuthorFoundationRevision)
            .where(AuthorFoundationRevision.novel_id == novel_id)
            .order_by(AuthorFoundationRevision.version.desc())
        )
        return list(result.scalars().all())

    async def create_foundation(self, novel_id: int, data: dict) -> AuthorFoundation:
        foundation = AuthorFoundation(novel_id=novel_id, **data)
        self.db.add(foundation)
        await self.db.flush()
        return foundation

    async def create_foundation_revision(self, novel_id: int, data: dict) -> AuthorFoundationRevision:
        revision = AuthorFoundationRevision(novel_id=novel_id, **data)
        self.db.add(revision)
        await self.db.flush()
        return revision

    async def get_plot_unit(self, unit_id: int, novel_id: int) -> Optional[PlotUnit]:
        result = await self.db.execute(
            select(PlotUnit).where(PlotUnit.id == unit_id, PlotUnit.novel_id == novel_id)
        )
        return result.scalar_one_or_none()

    async def list_plot_units(self, novel_id: int) -> list[PlotUnit]:
        result = await self.db.execute(
            select(PlotUnit)
            .where(PlotUnit.novel_id == novel_id)
            .order_by(PlotUnit.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_plot_unit(self, novel_id: int, data: dict) -> PlotUnit:
        unit = PlotUnit(novel_id=novel_id, **data)
        self.db.add(unit)
        await self.db.flush()
        return unit

    async def list_plan_revisions(self, plot_unit_id: int) -> list[PlotPlanRevision]:
        result = await self.db.execute(
            select(PlotPlanRevision)
            .where(PlotPlanRevision.plot_unit_id == plot_unit_id)
            .order_by(PlotPlanRevision.version.desc())
        )
        return list(result.scalars().all())

    async def get_plan_revision(self, revision_id: int, novel_id: int) -> Optional[PlotPlanRevision]:
        result = await self.db.execute(
            select(PlotPlanRevision).where(
                PlotPlanRevision.id == revision_id,
                PlotPlanRevision.novel_id == novel_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_plan_revision(self, novel_id: int, data: dict) -> PlotPlanRevision:
        revision = PlotPlanRevision(novel_id=novel_id, **data)
        self.db.add(revision)
        await self.db.flush()
        return revision

    async def archive_active_plans(self, plot_unit_id: int):
        await self.db.execute(
            update(PlotPlanRevision)
            .where(
                PlotPlanRevision.plot_unit_id == plot_unit_id,
                PlotPlanRevision.status == "active",
            )
            .values(status="superseded")
        )
        await self.db.flush()

    async def get_active_plan(self, plot_unit_id: int) -> Optional[PlotPlanRevision]:
        result = await self.db.execute(
            select(PlotPlanRevision).where(
                PlotPlanRevision.plot_unit_id == plot_unit_id,
                PlotPlanRevision.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def get_decision(self, decision_id: int, novel_id: int) -> Optional[PlanningDecision]:
        result = await self.db.execute(
            select(PlanningDecision).where(
                PlanningDecision.id == decision_id,
                PlanningDecision.novel_id == novel_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending_decisions(self, novel_id: int) -> list[PlanningDecision]:
        result = await self.db.execute(
            select(PlanningDecision).where(
                PlanningDecision.novel_id == novel_id,
                PlanningDecision.status == "pending",
            )
        )
        return list(result.scalars().all())

    async def list_decisions(self, novel_id: int, status: Optional[str] = None) -> list[PlanningDecision]:
        stmt = select(PlanningDecision).where(PlanningDecision.novel_id == novel_id)
        if status:
            stmt = stmt.where(PlanningDecision.status == status)
        stmt = stmt.order_by(PlanningDecision.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_decision(self, novel_id: int, data: dict) -> PlanningDecision:
        decision = PlanningDecision(novel_id=novel_id, **data)
        self.db.add(decision)
        await self.db.flush()
        return decision

    async def update_decision(self, decision: PlanningDecision, data: dict) -> PlanningDecision:
        for key, value in data.items():
            setattr(decision, key, value)
        await self.db.flush()
        return decision

    async def create_draft_revision(self, novel_id: int, data: dict) -> DraftRevision:
        revision = DraftRevision(novel_id=novel_id, **data)
        self.db.add(revision)
        await self.db.flush()
        return revision

    async def list_draft_revisions_by_run(self, writing_run_id: int) -> list[DraftRevision]:
        result = await self.db.execute(
            select(DraftRevision).where(DraftRevision.writing_run_id == writing_run_id)
        )
        return list(result.scalars().all())

    async def mark_plans_stale(self, novel_id: int):
        await self.db.execute(
            update(PlotPlanRevision)
            .where(
                PlotPlanRevision.novel_id == novel_id,
                PlotPlanRevision.status == "active",
            )
            .values(status="stale")
        )
        await self.db.flush()
