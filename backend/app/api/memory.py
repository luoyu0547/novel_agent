from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.memory import CharacterCreate, CharacterOut, CharacterUpdate, WorldSettingCreate, WorldSettingOut, WorldSettingUpdate
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/novels/{novel_id}", tags=["基础记忆"])


@router.get("/characters")
async def list_characters(novel_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    characters = await MemoryService(db).list_characters(current_user.id, novel_id)
    return ApiResponse.success(data=[CharacterOut.model_validate(c) for c in characters])


@router.post("/characters")
async def create_character(novel_id: int, body: CharacterCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    character = await MemoryService(db).create_character(current_user.id, novel_id, body)
    return ApiResponse.success(data=CharacterOut.model_validate(character), message="角色创建成功")


@router.get("/characters/{character_id}")
async def get_character(novel_id: int, character_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    character = await MemoryService(db).get_character(current_user.id, novel_id, character_id)
    return ApiResponse.success(data=CharacterOut.model_validate(character))


@router.put("/characters/{character_id}")
async def update_character(novel_id: int, character_id: int, body: CharacterUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    character = await MemoryService(db).update_character(current_user.id, novel_id, character_id, body)
    return ApiResponse.success(data=CharacterOut.model_validate(character), message="角色保存成功")


@router.delete("/characters/{character_id}")
async def delete_character(novel_id: int, character_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await MemoryService(db).delete_character(current_user.id, novel_id, character_id)
    return ApiResponse.success(message="角色删除成功")


@router.get("/settings")
async def list_settings(novel_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    settings = await MemoryService(db).list_settings(current_user.id, novel_id)
    return ApiResponse.success(data=[WorldSettingOut.model_validate(s) for s in settings])


@router.post("/settings")
async def create_setting(novel_id: int, body: WorldSettingCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    setting = await MemoryService(db).create_setting(current_user.id, novel_id, body)
    return ApiResponse.success(data=WorldSettingOut.model_validate(setting), message="设定创建成功")


@router.get("/settings/{setting_id}")
async def get_setting(novel_id: int, setting_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    setting = await MemoryService(db).get_setting(current_user.id, novel_id, setting_id)
    return ApiResponse.success(data=WorldSettingOut.model_validate(setting))


@router.put("/settings/{setting_id}")
async def update_setting(novel_id: int, setting_id: int, body: WorldSettingUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    setting = await MemoryService(db).update_setting(current_user.id, novel_id, setting_id, body)
    return ApiResponse.success(data=WorldSettingOut.model_validate(setting), message="设定保存成功")


@router.delete("/settings/{setting_id}")
async def delete_setting(novel_id: int, setting_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await MemoryService(db).delete_setting(current_user.id, novel_id, setting_id)
    return ApiResponse.success(message="设定删除成功")
