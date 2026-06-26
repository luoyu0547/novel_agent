from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.foreshadowing import Foreshadowing
from app.models.memory import CharacterProfile, WorldSetting
from app.models.pending_memory import PendingMemory
from app.models.plot_fact import PlotFact


class PendingMemoryRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int, status: str | None = None) -> list[PendingMemory]:
        stmt = select(PendingMemory).where(
            PendingMemory.novel_id == novel_id,
        ).order_by(PendingMemory.created_at.desc())
        if status:
            stmt = stmt.where(PendingMemory.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, memory_id: int) -> PendingMemory | None:
        return await self.db.get(PendingMemory, memory_id)

    async def create(self, novel_id: int, chapter_id: int, memory_type: str, content: dict) -> PendingMemory:
        pm = PendingMemory(
            novel_id=novel_id,
            chapter_id=chapter_id,
            memory_type=memory_type,
            content=content,
        )
        self.db.add(pm)
        await self.db.commit()
        await self.db.refresh(pm)
        return pm

    async def confirm(self, memory: PendingMemory) -> None:
        memory.status = "confirmed"
        data_list = memory.content.get("data", [])
        if memory.memory_type == "character_change":
            for change in data_list:
                stmt = select(CharacterProfile).where(
                    CharacterProfile.novel_id == memory.novel_id,
                    CharacterProfile.name == change["name"],
                )
                result = await self.db.execute(stmt)
                char = result.scalar_one_or_none()
                if char and (field := change.get("field")):
                    if hasattr(char, field):
                        setattr(char, field, change["change_description"])
        elif memory.memory_type == "world_setting":
            for s in data_list:
                ws = WorldSetting(
                    novel_id=memory.novel_id,
                    title=s["title"],
                    category=s.get("category", "other"),
                    content=s.get("content", ""),
                )
                self.db.add(ws)
        elif memory.memory_type == "plot_fact":
            for f in data_list:
                pf = PlotFact(
                    novel_id=memory.novel_id,
                    chapter_id=memory.chapter_id,
                    fact_type=f.get("fact_type", "event"),
                    content=f.get("description", f.get("event", "")),
                    related_characters=f.get("characters_involved", []),
                    importance=f.get("importance", "minor"),
                )
                self.db.add(pf)
        elif memory.memory_type == "foreshadowing":
            for c in data_list:
                fs = Foreshadowing(
                    novel_id=memory.novel_id,
                    name=c["name"],
                    planted_chapter_id=memory.chapter_id,
                    description=c.get("description", ""),
                    hidden_truth=c.get("hint", ""),
                    related_characters=c.get("related_characters", []),
                )
                self.db.add(fs)
        await self.db.commit()

    async def reject(self, memory: PendingMemory) -> None:
        memory.status = "rejected"
        await self.db.commit()
