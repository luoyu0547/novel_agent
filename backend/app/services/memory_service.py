"""角色资料和世界观设定的业务逻辑。通过 ensure_owned_novel 守卫所有权。"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.repositories.memory_repo import CharacterRepo, WorldSettingRepo
from app.repositories.novel_repo import NovelRepo
from app.schemas.memory import CharacterCreate, CharacterUpdate, WorldSettingCreate, WorldSettingUpdate


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.novel_repo = NovelRepo(db)
        self.character_repo = CharacterRepo(db)
        self.setting_repo = WorldSettingRepo(db)

    async def ensure_owned_novel(self, user_id: int, novel_id: int):
        """验证小说存在且属于当前用户。所有权不匹配时也返回 NotFound（避免泄露小说是否存在）。"""
        novel = await self.novel_repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise NotFound("小说不存在")
        return novel

    async def list_characters(self, user_id: int, novel_id: int):
        await self.ensure_owned_novel(user_id, novel_id)
        return await self.character_repo.list_by_novel(novel_id)

    async def create_character(self, user_id: int, novel_id: int, body: CharacterCreate):
        await self.ensure_owned_novel(user_id, novel_id)
        return await self.character_repo.create(novel_id, body.model_dump())

    async def get_character(self, user_id: int, novel_id: int, character_id: int):
        await self.ensure_owned_novel(user_id, novel_id)
        character = await self.character_repo.get_by_id(character_id)
        if not character or character.novel_id != novel_id:
            raise NotFound("角色不存在")
        return character

    async def update_character(self, user_id: int, novel_id: int, character_id: int, body: CharacterUpdate):
        character = await self.get_character(user_id, novel_id, character_id)
        return await self.character_repo.update(character, body.model_dump(exclude_unset=True))

    async def delete_character(self, user_id: int, novel_id: int, character_id: int):
        character = await self.get_character(user_id, novel_id, character_id)
        await self.character_repo.delete(character)

    async def list_settings(self, user_id: int, novel_id: int):
        await self.ensure_owned_novel(user_id, novel_id)
        return await self.setting_repo.list_by_novel(novel_id)

    async def create_setting(self, user_id: int, novel_id: int, body: WorldSettingCreate):
        await self.ensure_owned_novel(user_id, novel_id)
        return await self.setting_repo.create(novel_id, body.model_dump())

    async def get_setting(self, user_id: int, novel_id: int, setting_id: int):
        await self.ensure_owned_novel(user_id, novel_id)
        setting = await self.setting_repo.get_by_id(setting_id)
        if not setting or setting.novel_id != novel_id:
            raise NotFound("设定不存在")
        return setting

    async def update_setting(self, user_id: int, novel_id: int, setting_id: int, body: WorldSettingUpdate):
        setting = await self.get_setting(user_id, novel_id, setting_id)
        return await self.setting_repo.update(setting, body.model_dump(exclude_unset=True))

    async def delete_setting(self, user_id: int, novel_id: int, setting_id: int):
        setting = await self.get_setting(user_id, novel_id, setting_id)
        await self.setting_repo.delete(setting)
