from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import CharacterProfile, WorldSetting


class CharacterRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int) -> list[CharacterProfile]:
        result = await self.db.execute(select(CharacterProfile).where(CharacterProfile.novel_id == novel_id).order_by(CharacterProfile.updated_at.desc()))
        return list(result.scalars().all())

    async def get_by_id(self, character_id: int) -> Optional[CharacterProfile]:
        return await self.db.get(CharacterProfile, character_id)

    async def create(self, novel_id: int, data: dict) -> CharacterProfile:
        character = CharacterProfile(novel_id=novel_id, **data)
        self.db.add(character)
        await self.db.commit()
        await self.db.refresh(character)
        return character

    async def update(self, character: CharacterProfile, data: dict) -> CharacterProfile:
        for key, value in data.items():
            if value is not None:
                setattr(character, key, value)
        await self.db.commit()
        await self.db.refresh(character)
        return character

    async def delete(self, character: CharacterProfile) -> None:
        await self.db.delete(character)
        await self.db.commit()


class WorldSettingRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int) -> list[WorldSetting]:
        result = await self.db.execute(select(WorldSetting).where(WorldSetting.novel_id == novel_id).order_by(WorldSetting.updated_at.desc()))
        return list(result.scalars().all())

    async def get_by_id(self, setting_id: int) -> Optional[WorldSetting]:
        return await self.db.get(WorldSetting, setting_id)

    async def create(self, novel_id: int, data: dict) -> WorldSetting:
        setting = WorldSetting(novel_id=novel_id, **data)
        self.db.add(setting)
        await self.db.commit()
        await self.db.refresh(setting)
        return setting

    async def update(self, setting: WorldSetting, data: dict) -> WorldSetting:
        for key, value in data.items():
            if value is not None:
                setattr(setting, key, value)
        await self.db.commit()
        await self.db.refresh(setting)
        return setting

    async def delete(self, setting: WorldSetting) -> None:
        await self.db.delete(setting)
        await self.db.commit()
