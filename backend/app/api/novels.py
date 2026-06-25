from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.models.user import User
from app.core.security import get_current_user
from app.schemas.novel import (
    ChapterCreate,
    ChapterOut,
    ChapterUpdate,
    NovelCreate,
    NovelListItem,
    NovelOut,
    NovelUpdate,
)
from app.services.novel_service import NovelService

router = APIRouter(prefix="/novels", tags=["小说"])


@router.get("")
async def list_novels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    novels = await NovelService(db).list(current_user.id)
    return ApiResponse.success(data=[NovelListItem.model_validate(n) for n in novels])


@router.post("")
async def create_novel(
    body: NovelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    novel = await NovelService(db).create(current_user.id, body.title, body.description)
    return ApiResponse.success(data=NovelListItem.model_validate(novel), message="小说创建成功")


@router.get("/{novel_id}")
async def get_novel(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    novel = await NovelService(db).get(novel_id, current_user.id)
    return ApiResponse.success(data=NovelOut.model_validate(novel))


@router.put("/{novel_id}")
async def update_novel(
    novel_id: int,
    body: NovelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    novel = await NovelService(db).update(current_user.id, novel_id, body.title, body.description)
    return ApiResponse.success(data=NovelOut.model_validate(novel), message="小说更新成功")


@router.delete("/{novel_id}")
async def delete_novel(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).delete(current_user.id, novel_id)
    return ApiResponse.success(message="小说删除成功")


@router.post("/{novel_id}/chapters")
async def create_chapter(
    novel_id: int,
    body: ChapterCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chapter = await NovelService(db).create_chapter(current_user.id, novel_id, body.title, body.content)
    return ApiResponse.success(data=ChapterOut.model_validate(chapter), message="章节创建成功")


@router.get("/{novel_id}/chapters/{chapter_id}")
async def get_chapter(
    novel_id: int,
    chapter_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chapter = await NovelService(db).get_chapter(novel_id, chapter_id, current_user.id)
    return ApiResponse.success(data=ChapterOut.model_validate(chapter))


@router.put("/{novel_id}/chapters/{chapter_id}")
async def update_chapter(
    novel_id: int,
    chapter_id: int,
    body: ChapterUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chapter = await NovelService(db).update_chapter(current_user.id, novel_id, chapter_id, body.title, body.content)
    return ApiResponse.success(data=ChapterOut.model_validate(chapter), message="章节保存成功")


@router.delete("/{novel_id}/chapters/{chapter_id}")
async def delete_chapter(
    novel_id: int,
    chapter_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).delete_chapter(current_user.id, novel_id, chapter_id)
    return ApiResponse.success(message="章节删除成功")
