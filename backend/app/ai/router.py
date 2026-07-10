from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import DeepSeekExtractionService
from app.core.database import get_db
from app.core.exceptions import NotFound
from app.core.response import ApiResponse
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.pending_memory_repo import PendingMemoryRepo
from app.schemas.pending_memory import (
    ExtractRequest,
    ExtractResponse,
    PendingMemoryBatchBody,
    PendingMemoryOut,
)
from app.services.novel_service import NovelService

router = APIRouter(prefix="/novels/{novel_id}", tags=["AI"])

extraction_service = DeepSeekExtractionService()


@router.post("/chapters/{chapter_id}/extract")
async def extract_chapter(
    novel_id: int,
    chapter_id: int,
    body: ExtractRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).get(novel_id, current_user.id)
    result = await extraction_service.extract(
        novel_id=novel_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        mode=body.mode,
    )
    return ApiResponse.success(data=ExtractResponse(**result).model_dump())


@router.get("/pending-memories")
async def list_pending_memories(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).get(novel_id, current_user.id)
    repo = PendingMemoryRepo(db)
    memories = await repo.list_by_novel(novel_id)
    return ApiResponse.success(
        data=[PendingMemoryOut.model_validate(m) for m in memories]
    )


@router.put("/pending-memories/{memory_id}/confirm")
async def confirm_pending_memory(
    novel_id: int,
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).get(novel_id, current_user.id)
    repo = PendingMemoryRepo(db)
    memory = await repo.get(memory_id)
    if not memory or memory.novel_id != novel_id:
        raise NotFound("待确认记忆不存在")
    await repo.confirm(memory)
    return ApiResponse.success(message="已确认并写入正式记忆")


@router.put("/pending-memories/{memory_id}/reject")
async def reject_pending_memory(
    novel_id: int,
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).get(novel_id, current_user.id)
    repo = PendingMemoryRepo(db)
    memory = await repo.get(memory_id)
    if not memory or memory.novel_id != novel_id:
        raise NotFound("待确认记忆不存在")
    await repo.reject(memory)
    return ApiResponse.success(message="已拒绝")


@router.put("/pending-memories/batch")
async def batch_pending_memories(
    novel_id: int,
    body: PendingMemoryBatchBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).get(novel_id, current_user.id)
    repo = PendingMemoryRepo(db)
    memories = await repo.get_many(body.ids)
    for memory in memories:
        if memory.novel_id != novel_id:
            continue
        if body.action == "confirm":
            await repo.confirm(memory)
        elif body.action == "reject":
            await repo.reject(memory)
    return ApiResponse.success(message=f"批量{body.action}完成")
