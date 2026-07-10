from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.writing import (
    NovelBlueprint,
    ChapterPlan,
    ChapterBrief,
    ContextPackage,
    WritingRun,
)


class BlueprintRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int) -> list[NovelBlueprint]:
        result = await self.db.execute(
            select(NovelBlueprint)
            .where(NovelBlueprint.novel_id == novel_id)
            .order_by(NovelBlueprint.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, blueprint_id: int) -> Optional[NovelBlueprint]:
        return await self.db.get(NovelBlueprint, blueprint_id)

    async def get_active(self, novel_id: int) -> Optional[NovelBlueprint]:
        result = await self.db.execute(
            select(NovelBlueprint).where(
                NovelBlueprint.novel_id == novel_id,
                NovelBlueprint.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def create(self, novel_id: int, data: dict) -> NovelBlueprint:
        blueprint = NovelBlueprint(novel_id=novel_id, **data)
        self.db.add(blueprint)
        await self.db.flush()
        return blueprint

    async def update(self, blueprint: NovelBlueprint, data: dict) -> NovelBlueprint:
        for key, value in data.items():
            setattr(blueprint, key, value)
        await self.db.flush()
        return blueprint

    async def deactivate_all(self, novel_id: int):
        await self.db.execute(
            update(NovelBlueprint)
            .where(
                NovelBlueprint.novel_id == novel_id,
                NovelBlueprint.status == "active",
            )
            .values(status="archived")
        )
        await self.db.flush()


class ChapterPlanRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int, active_only: bool = False) -> list[ChapterPlan]:
        stmt = (
            select(ChapterPlan)
            .where(ChapterPlan.novel_id == novel_id)
            .order_by(ChapterPlan.position.asc())
        )
        if active_only:
            stmt = stmt.where(ChapterPlan.status == "ready")
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest(self, novel_id: int) -> Optional[ChapterPlan]:
        result = await self.db.execute(
            select(ChapterPlan)
            .where(ChapterPlan.novel_id == novel_id)
            .order_by(ChapterPlan.position.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, plan_id: int) -> Optional[ChapterPlan]:
        return await self.db.get(ChapterPlan, plan_id)

    async def create(self, novel_id: int, data: dict) -> ChapterPlan:
        plan = ChapterPlan(novel_id=novel_id, **data)
        self.db.add(plan)
        await self.db.flush()
        return plan

    async def update(self, plan: ChapterPlan, data: dict) -> ChapterPlan:
        for key, value in data.items():
            setattr(plan, key, value)
        await self.db.flush()
        return plan


class ChapterBriefRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, brief_id: int) -> Optional[ChapterBrief]:
        return await self.db.get(ChapterBrief, brief_id)

    async def create(self, novel_id: int, data: dict) -> ChapterBrief:
        brief = ChapterBrief(novel_id=novel_id, **data)
        self.db.add(brief)
        await self.db.flush()
        return brief

    async def update(self, brief: ChapterBrief, data: dict) -> ChapterBrief:
        for key, value in data.items():
            setattr(brief, key, value)
        await self.db.flush()
        return brief


class ContextPackageRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, package_id: int) -> Optional[ContextPackage]:
        return await self.db.get(ContextPackage, package_id)

    async def create(self, novel_id: int, data: dict) -> ContextPackage:
        package = ContextPackage(novel_id=novel_id, **data)
        self.db.add(package)
        await self.db.flush()
        return package


class WritingRunRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int) -> list[WritingRun]:
        result = await self.db.execute(
            select(WritingRun)
            .where(WritingRun.novel_id == novel_id)
            .order_by(WritingRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, run_id: int) -> Optional[WritingRun]:
        return await self.db.get(WritingRun, run_id)

    async def create(self, novel_id: int, data: dict) -> WritingRun:
        run = WritingRun(novel_id=novel_id, **data)
        self.db.add(run)
        await self.db.flush()
        return run

    async def update(self, run: WritingRun, data: dict) -> WritingRun:
        for key, value in data.items():
            setattr(run, key, value)
        await self.db.flush()
        return run
