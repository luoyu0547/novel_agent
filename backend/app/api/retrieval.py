"""Retrieval index control-plane API.

Provides endpoints for checking index status and requesting rebuilds.
Both endpoints enforce novel ownership (NotFound for missing or foreign novel).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFound
from app.core.response import ApiResponse
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.retrieval import RetrievalIndexStatusOut, RetrievalRebuildOut
from app.services.novel_service import NovelService
from app.services.retrieval_index_service import RetrievalIndexService

router = APIRouter(prefix="/novels/{novel_id}", tags=["检索索引"])


@router.get("/retrieval-index")
async def get_retrieval_index_status(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest retrieval index job status for a novel."""
    await NovelService(db).get(novel_id, current_user.id)
    job = await RetrievalIndexService(db).status(novel_id, current_user.id)
    if job is None:
        return ApiResponse.success(data=None)
    return ApiResponse.success(data=RetrievalIndexStatusOut.model_validate(job).model_dump())


@router.post("/retrieval-index/rebuild")
async def rebuild_retrieval_index(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request a full rebuild of the retrieval index for a novel."""
    await NovelService(db).get(novel_id, current_user.id)
    job = await RetrievalIndexService(db).request_rebuild(novel_id, current_user.id)
    return ApiResponse.success(
        data=RetrievalRebuildOut(job_id=job.id, status=job.status).model_dump(),
        message="索引重建已请求",
    )
