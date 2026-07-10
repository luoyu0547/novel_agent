from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.planning import VolumeArc, PlanVersion


class VolumeArcRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int) -> list[VolumeArc]:
        result = await self.db.execute(
            select(VolumeArc)
            .where(VolumeArc.novel_id == novel_id)
            .order_by(VolumeArc.order_index)
        )
        return list(result.scalars().all())

    async def get_by_id(self, arc_id: int) -> Optional[VolumeArc]:
        return await self.db.get(VolumeArc, arc_id)

    async def get_active(self, novel_id: int) -> Optional[VolumeArc]:
        result = await self.db.execute(
            select(VolumeArc).where(
                VolumeArc.novel_id == novel_id,
                VolumeArc.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def create(self, novel_id: int, data: dict) -> VolumeArc:
        arc = VolumeArc(novel_id=novel_id, **data)
        self.db.add(arc)
        await self.db.flush()
        return arc

    async def update(self, arc: VolumeArc, data: dict) -> VolumeArc:
        for key, value in data.items():
            setattr(arc, key, value)
        await self.db.flush()
        return arc

    async def deactivate_all(self, novel_id: int):
        await self.db.execute(
            update(VolumeArc)
            .where(
                VolumeArc.novel_id == novel_id,
                VolumeArc.status == "active",
            )
            .values(status="archived")
        )
        await self.db.flush()


class PlanVersionRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int) -> list[PlanVersion]:
        result = await self.db.execute(
            select(PlanVersion)
            .where(PlanVersion.novel_id == novel_id)
            .order_by(PlanVersion.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_entity(self, plan_type: str, plan_id: int) -> list[PlanVersion]:
        result = await self.db.execute(
            select(PlanVersion)
            .where(
                PlanVersion.plan_type == plan_type,
                PlanVersion.plan_id == plan_id,
            )
            .order_by(PlanVersion.version.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, version_id: int) -> Optional[PlanVersion]:
        return await self.db.get(PlanVersion, version_id)

    async def get_current(self, plan_type: str, plan_id: int) -> Optional[PlanVersion]:
        result = await self.db.execute(
            select(PlanVersion).where(
                PlanVersion.plan_type == plan_type,
                PlanVersion.plan_id == plan_id,
                PlanVersion.status == "current",
            )
        )
        return result.scalar_one_or_none()

    async def create(self, novel_id: int, data: dict) -> PlanVersion:
        version = PlanVersion(novel_id=novel_id, **data)
        self.db.add(version)
        await self.db.flush()
        return version

    async def archive_all(self, plan_type: str, plan_id: int):
        await self.db.execute(
            update(PlanVersion)
            .where(
                PlanVersion.plan_type == plan_type,
                PlanVersion.plan_id == plan_id,
                PlanVersion.status == "current",
            )
            .values(status="archived")
        )
        await self.db.flush()

    async def update_status(self, version: PlanVersion, status: str) -> PlanVersion:
        version.status = status
        await self.db.flush()
        return version
