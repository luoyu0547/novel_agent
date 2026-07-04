from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.writing import RepairLog, PendingRepair


class RepairLogRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, novel_id: int, writing_run_id: int, data: dict) -> RepairLog:
        log = RepairLog(novel_id=novel_id, writing_run_id=writing_run_id, **data)
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_by_writing_run(self, writing_run_id: int) -> list[RepairLog]:
        result = await self.db.execute(
            select(RepairLog)
            .where(RepairLog.writing_run_id == writing_run_id)
            .order_by(RepairLog.created_at.asc())
        )
        return list(result.scalars().all())

    async def cleanup_by_writing_run(self, writing_run_id: int):
        logs = await self.list_by_writing_run(writing_run_id)
        for log in logs:
            await self.db.delete(log)
        await self.db.flush()


class PendingRepairRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, novel_id: int, chapter_id: int, writing_run_id: int, data: dict) -> PendingRepair:
        repair = PendingRepair(novel_id=novel_id, chapter_id=chapter_id, writing_run_id=writing_run_id, **data)
        self.db.add(repair)
        await self.db.flush()
        return repair

    async def get_by_id(self, repair_id: int) -> Optional[PendingRepair]:
        return await self.db.get(PendingRepair, repair_id)

    async def list_by_writing_run(self, writing_run_id: int) -> list[PendingRepair]:
        result = await self.db.execute(
            select(PendingRepair)
            .where(PendingRepair.writing_run_id == writing_run_id)
            .order_by(PendingRepair.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_pending_by_writing_run(self, writing_run_id: int) -> list[PendingRepair]:
        result = await self.db.execute(
            select(PendingRepair)
            .where(PendingRepair.writing_run_id == writing_run_id, PendingRepair.status == "pending")
            .order_by(PendingRepair.created_at.asc())
        )
        return list(result.scalars().all())

    async def update_status(self, repair_id: int, status: str) -> PendingRepair:
        repair = await self.get_by_id(repair_id)
        if repair:
            repair.status = status
            await self.db.flush()
        return repair

    async def cleanup_by_writing_run(self, writing_run_id: int):
        repairs = await self.list_by_writing_run(writing_run_id)
        for r in repairs:
            await self.db.delete(r)
        await self.db.flush()
