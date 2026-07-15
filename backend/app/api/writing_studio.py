"""Phase 6 Author Studio — REST endpoints.

Exposes session lifecycle, message handling, action confirmation,
working-copy persistence, and source snapshot projection through
seven nested Studio endpoints plus the GET sources route.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequest
from app.core.response import ApiResponse
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.writing_studio import (
    CreateWritingSessionRequest,
    DraftWorkingCopyOut,
    StudioActionRequest,
    StudioMessageCreateRequest,
    WorkingCopySaveRequest,
    WritingSessionOut,
)
from app.services.working_copy_service import WorkingCopyService
from app.services.writing_session_service import WritingSessionService
from app.services.writing_studio_service import WritingStudioService

router = APIRouter(prefix="/novels/{novel_id}", tags=["Writing Studio"])


def get_studio_service(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WritingStudioService:
    return WritingStudioService(db, current_user.id, novel_id)


StudioSvc = Annotated[WritingStudioService, Depends(get_studio_service)]


@router.post("/writing-sessions")
async def create_session(
    novel_id: int,
    body: CreateWritingSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await WritingSessionService(db, current_user.id, novel_id).create_session(
        body.target_chapter_id, body.title,
    )
    return ApiResponse.success(data=WritingSessionOut.model_validate(session).model_dump())


@router.get("/writing-sessions")
async def list_sessions(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions = await WritingSessionService(db, current_user.id, novel_id).list_sessions()
    return ApiResponse.success(data=[WritingSessionOut.model_validate(item).model_dump() for item in sessions])


@router.get("/writing-sessions/{session_id}")
async def get_session(
    novel_id: int,
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WritingSessionService(db, current_user.id, novel_id)
    session = await service.get_session(session_id)
    return ApiResponse.success(data=await service.to_workspace_out(session))


@router.post("/writing-sessions/{session_id}/messages")
async def send_message(
    novel_id: int,
    session_id: int,
    body: StudioMessageCreateRequest,
    studio_svc: StudioSvc,
):
    result = await studio_svc.send_author_message(
        session_id, body.text, body.idempotency_key,
    )
    return ApiResponse.success(data=result.model_dump())


@router.post("/writing-sessions/{session_id}/actions/{message_id}")
async def confirm_action(
    novel_id: int,
    session_id: int,
    message_id: int,
    body: StudioActionRequest,
    studio_svc: StudioSvc,
):
    result = await studio_svc.confirm_action(
        session_id, message_id, body.action, body.payload,
    )
    return ApiResponse.success(data=result.model_dump())


@router.put("/writing-sessions/{session_id}/working-copy")
async def save_working_copy(
    novel_id: int,
    session_id: int,
    body: WorkingCopySaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await WritingSessionService(db, current_user.id, novel_id).get_session(session_id)
    if session.active_writing_run_id is None:
        raise BadRequest("当前会话没有可保存的草稿")
    copy = await WorkingCopyService(db, current_user.id, novel_id).save(
        session.active_writing_run_id, body.title, body.content, body.base_revision_sequence,
    )
    return ApiResponse.success(data=DraftWorkingCopyOut.model_validate(copy).model_dump())


@router.get("/writing-runs/{run_id}/sources")
async def get_run_sources(
    novel_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sources = await WritingSessionService(db, current_user.id, novel_id).get_sources(run_id)
    return ApiResponse.success(data=[item.model_dump() for item in sources])
