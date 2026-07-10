from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException, NotFound
from app.core.response import ApiResponse
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.planning import (
    VolumeArcOut,
    VolumeArcCreateRequest,
    VolumeArcUpdateRequest,
    PlanVersionOut,
    PlanVersionCreateRequest,
)
from app.services.planning_service import PlanningService

router = APIRouter(prefix="/novels/{novel_id}", tags=["Planning"])


def _get_service(db: AsyncSession, current_user: User, novel_id: int) -> PlanningService:
    return PlanningService(db=db, user_id=current_user.id, novel_id=novel_id)


# ── Dashboard ──────────────────────────────────────────────────────────────


@router.get("/planning/dashboard")
async def planning_dashboard(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    dashboard = await svc.get_planning_dashboard()
    return ApiResponse.success(data=dashboard)


# ── Volume Arcs ────────────────────────────────────────────────────────────


@router.post("/planning/volume-arcs")
async def create_volume_arc(
    novel_id: int,
    body: VolumeArcCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    arc = await svc.create_volume_arc(data)
    return ApiResponse.success(data=VolumeArcOut.model_validate(arc).model_dump())


@router.get("/planning/volume-arcs")
async def list_volume_arcs(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    arcs = await svc.list_volume_arcs()
    return ApiResponse.success(data=[VolumeArcOut.model_validate(a).model_dump() for a in arcs])


@router.get("/planning/volume-arcs/{arc_id}")
async def get_volume_arc(
    novel_id: int,
    arc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    arc = await svc.get_volume_arc(arc_id)
    return ApiResponse.success(data=VolumeArcOut.model_validate(arc).model_dump())


@router.put("/planning/volume-arcs/{arc_id}")
async def update_volume_arc(
    novel_id: int,
    arc_id: int,
    body: VolumeArcUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    arc = await svc.update_volume_arc(arc_id, data)
    return ApiResponse.success(data=VolumeArcOut.model_validate(arc).model_dump())


@router.put("/planning/volume-arcs/{arc_id}/activate")
async def activate_volume_arc(
    novel_id: int,
    arc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    arc = await svc.activate_volume_arc(arc_id)
    return ApiResponse.success(data=VolumeArcOut.model_validate(arc).model_dump())


# ── Plan Versions ──────────────────────────────────────────────────────────


@router.post("/planning/plan-versions")
async def create_plan_version(
    novel_id: int,
    body: PlanVersionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    data = body.model_dump()
    version = await svc.create_plan_version(data)
    return ApiResponse.success(data=PlanVersionOut.model_validate(version).model_dump())


@router.get("/planning/plan-versions")
async def list_plan_versions(
    novel_id: int,
    plan_type: str = Query(..., description="计划类型"),
    plan_id: int = Query(..., description="计划ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    versions = await svc.list_plan_versions(plan_type, plan_id)
    return ApiResponse.success(data=[PlanVersionOut.model_validate(v).model_dump() for v in versions])


@router.put("/planning/plan-versions/{version_id}/activate")
async def activate_plan_version(
    novel_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    version = await svc.activate_plan_version(version_id)
    return ApiResponse.success(data=PlanVersionOut.model_validate(version).model_dump())
