from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.response import ApiResponse
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.plot_planning import (
    AuthorFoundationOut,
    AuthorFoundationRevisionOut,
    AuthorFoundationUpdateRequest,
    ChooseDecisionRequest,
    DraftRevisionOut,
    PlotUnitCreateRequest,
    PlotUnitOut,
    PlotPlanRevisionOut,
    PlanningDecisionOut,
)
from app.services.plot_planning_service import PlotPlanningService

router = APIRouter(prefix="/novels/{novel_id}", tags=["Planning"])


def _get_service(db: AsyncSession, current_user: User, novel_id: int) -> PlotPlanningService:
    return PlotPlanningService(db=db, user_id=current_user.id, novel_id=novel_id)


@router.get("/author-foundation")
async def get_author_foundation(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    foundation = await svc.get_foundation()
    return ApiResponse.success(data=AuthorFoundationOut.model_validate(foundation).model_dump())


@router.put("/author-foundation")
async def update_author_foundation(
    novel_id: int,
    body: AuthorFoundationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    foundation = await svc.update_foundation(data, change_reason="manual_update")
    return ApiResponse.success(data=AuthorFoundationOut.model_validate(foundation).model_dump())


@router.get("/author-foundation/revisions")
async def list_foundation_revisions(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    revisions = await svc.list_foundation_revisions()
    return ApiResponse.success(
        data=[AuthorFoundationRevisionOut.model_validate(r).model_dump() for r in revisions]
    )


@router.post("/plot-units")
async def create_plot_unit(
    novel_id: int,
    body: PlotUnitCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    unit = await svc.create_plot_unit(body.model_dump())
    return ApiResponse.success(data=PlotUnitOut.model_validate(unit).model_dump())


@router.get("/plot-units")
async def list_plot_units(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    units = await svc.list_plot_units()
    return ApiResponse.success(data=[PlotUnitOut.model_validate(u).model_dump() for u in units])


@router.get("/plot-units/{plot_unit_id}")
async def get_plot_unit(
    novel_id: int,
    plot_unit_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    unit = await svc.get_plot_unit(plot_unit_id)
    return ApiResponse.success(data=PlotUnitOut.model_validate(unit).model_dump())


@router.post("/plot-units/{plot_unit_id}/plans/generate")
async def generate_plan(
    novel_id: int,
    plot_unit_id: int,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    plan = await svc.generate_plan(plot_unit_id, author_input=body.get("author_input", ""))
    return ApiResponse.success(data=PlotPlanRevisionOut.model_validate(plan).model_dump())


@router.get("/plot-units/{plot_unit_id}/plans")
async def list_plan_revisions(
    novel_id: int,
    plot_unit_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    plans = await svc.list_plan_revisions(plot_unit_id)
    return ApiResponse.success(data=[PlotPlanRevisionOut.model_validate(p).model_dump() for p in plans])


@router.put("/plot-units/{plot_unit_id}/plans/{revision_id}/confirm")
async def confirm_plan(
    novel_id: int,
    plot_unit_id: int,
    revision_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    plan = await svc.confirm_plan(plot_unit_id, revision_id)
    return ApiResponse.success(data=PlotPlanRevisionOut.model_validate(plan).model_dump())


@router.get("/planning-decisions")
async def list_planning_decisions(
    novel_id: int,
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    decisions = await svc.list_decisions(status=status)
    return ApiResponse.success(
        data=[PlanningDecisionOut.model_validate(d).model_dump() for d in decisions]
    )


@router.get("/planning-decisions/{decision_id}")
async def get_planning_decision(
    novel_id: int,
    decision_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    decision = await svc.get_decision(decision_id)
    return ApiResponse.success(data=PlanningDecisionOut.model_validate(decision).model_dump())


@router.put("/planning-decisions/{decision_id}/choose")
async def choose_decision(
    novel_id: int,
    decision_id: int,
    body: ChooseDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    decision, new_plan, revision, run = await svc.choose_decision(
        decision_id,
        option_index=body.option_index,
        custom_intent=body.custom_intent,
    )
    return ApiResponse.success(data={
        "decision": PlanningDecisionOut.model_validate(decision).model_dump(),
        "new_plan": PlotPlanRevisionOut.model_validate(new_plan).model_dump() if new_plan else None,
        "draft_revision": DraftRevisionOut.model_validate(revision).model_dump(),
    })
