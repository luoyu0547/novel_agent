from fastapi import APIRouter, Depends
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException, NotFound
from app.core.response import ApiResponse
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.quality_gate_repo import RepairLogRepo, PendingRepairRepo
from app.schemas.writing import (
    BlueprintGenerateRequest,
    BlueprintUpdateRequest,
    ChapterPlanUpdateRequest,
    ChapterBriefGenerateRequest,
    ChapterBriefUpdateRequest,
    ContextPackageGenerateRequest,
    WritingRunCreateRequest,
    NovelBlueprintOut,
    ChapterPlanOut,
    ChapterBriefOut,
    ContextPackageOut,
    WritingRunOut,
    RepairLogOut,
    PendingRepairOut,
    ResolveRepairRequest,
)
from app.schemas.revision import AcceptWritingRunRequest
from app.services.writing_service import WritingService
from app.services.repair_service import RepairService
from app.retrieval.runtime import get_retrieval_provider

router = APIRouter(prefix="/novels/{novel_id}", tags=["Writing"])


def _public_context_package_json(package_json: dict) -> dict:
    """Return only author-facing structured anchors for the legacy endpoint."""
    return {
        key: value
        for key, value in package_json.items()
        if key not in {"retrieved_context", "risk_guard", "snapshot"}
    }


def _get_service(db: AsyncSession, current_user: User, novel_id: int) -> WritingService:
    return WritingService(
        db=db,
        user_id=current_user.id,
        novel_id=novel_id,
        retrieval=get_retrieval_provider(),
    )


# ---- Blueprints ----


@router.post("/blueprints/generate")
async def generate_blueprint(
    novel_id: int,
    body: BlueprintGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    blueprint = await svc.generate_blueprint(body.author_input)
    return ApiResponse.success(data=NovelBlueprintOut.model_validate(blueprint).model_dump())


@router.get("/blueprints")
async def list_blueprints(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    blueprints = await svc.get_blueprints()
    return ApiResponse.success(data=[NovelBlueprintOut.model_validate(b).model_dump() for b in blueprints])


@router.put("/blueprints/{blueprint_id}")
async def update_blueprint(
    novel_id: int,
    blueprint_id: int,
    body: BlueprintUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    blueprint = await svc.update_blueprint(blueprint_id, data)
    return ApiResponse.success(data=NovelBlueprintOut.model_validate(blueprint).model_dump())


@router.put("/blueprints/{blueprint_id}/activate")
async def activate_blueprint(
    novel_id: int,
    blueprint_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    blueprint = await svc.activate_blueprint(blueprint_id)
    return ApiResponse.success(data=NovelBlueprintOut.model_validate(blueprint).model_dump())


# ---- Chapter Plans ----


@router.post("/chapter-plans/next/generate")
async def generate_chapter_plan(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    plan = await svc.generate_chapter_plan()
    return ApiResponse.success(data=ChapterPlanOut.model_validate(plan).model_dump())


@router.put("/chapter-plans/{plan_id}")
async def update_chapter_plan(
    novel_id: int,
    plan_id: int,
    body: ChapterPlanUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    plan = await svc.update_chapter_plan(plan_id, data)
    return ApiResponse.success(data=ChapterPlanOut.model_validate(plan).model_dump())


# ---- Chapter Briefs ----


@router.post("/chapter-briefs/generate")
async def generate_chapter_brief(
    novel_id: int,
    body: ChapterBriefGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    brief = await svc.generate_chapter_brief(
        body.chapter_plan_id,
        body.plot_plan_revision_id,
        body.author_input or "",
    )
    return ApiResponse.success(data=ChapterBriefOut.model_validate(brief).model_dump())


@router.put("/chapter-briefs/{brief_id}")
async def update_chapter_brief(
    novel_id: int,
    brief_id: int,
    body: ChapterBriefUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    brief = await svc.update_chapter_brief(brief_id, data)
    return ApiResponse.success(data=ChapterBriefOut.model_validate(brief).model_dump())


# ---- Context Packages ----


@router.post("/context-packages/generate")
async def generate_context_package(
    novel_id: int,
    body: ContextPackageGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    package = await svc.generate_context_package(
        body.chapter_brief_id,
        body.plot_plan_revision_id,
        body.author_input or "",
    )
    payload = ContextPackageOut.model_validate(package).model_dump()
    payload["package_json"] = _public_context_package_json(payload["package_json"])
    return ApiResponse.success(data=payload)


# ---- Writing Runs ----


@router.post("/writing-runs")
async def create_writing_run(
    novel_id: int,
    body: WritingRunCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    run = await svc.create_writing_run(
        body.chapter_brief_id,
        body.context_package_id,
        body.plot_plan_revision_id,
        body.author_input or "",
    )
    return ApiResponse.success(data=WritingRunOut.model_validate(run).model_dump())


@router.get("/writing-runs")
async def list_writing_runs(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    runs = await svc.get_writing_runs()
    return ApiResponse.success(data=[WritingRunOut.model_validate(r).model_dump() for r in runs])


@router.get("/writing-runs/{run_id}")
async def get_writing_run(
    novel_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    run = await svc.get_writing_run(run_id)
    return ApiResponse.success(data=WritingRunOut.model_validate(run).model_dump())


@router.put("/writing-runs/{run_id}/accept")
async def accept_writing_run(
    novel_id: int,
    run_id: int,
    body: Optional[AcceptWritingRunRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    req = body or AcceptWritingRunRequest()
    svc = _get_service(db, current_user, novel_id)
    chapter, extraction = await svc.accept_writing_run(
        run_id,
        force_accept=req.force_accept,
        force_reason=req.force_reason,
    )
    from app.schemas.novel import ChapterOut
    return ApiResponse.success(data={
        "chapter": ChapterOut.model_validate(chapter).model_dump(),
        "extraction": extraction,
    }, message="草稿已接受并写入章节")


@router.put("/writing-runs/{run_id}/discard")
async def discard_writing_run(
    novel_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    await svc.discard_writing_run(run_id)
    return ApiResponse.success(message="草稿已废弃")


@router.get("/writing-runs/{run_id}/repairs")
async def list_repairs(
    novel_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    run = await svc.get_writing_run(run_id)
    log_repo = RepairLogRepo(db)
    pending_repo = PendingRepairRepo(db)
    logs = await log_repo.list_by_writing_run(run_id)
    pending = await pending_repo.list_by_writing_run(run_id)
    return ApiResponse.success(data={
        "repair_logs": [RepairLogOut.model_validate(l).model_dump() for l in logs],
        "pending_repairs": [PendingRepairOut.model_validate(p).model_dump() for p in pending],
    })


@router.get("/writing-runs/{run_id}/repairs/pending")
async def list_pending_repairs(
    novel_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    await svc.get_writing_run(run_id)
    pending_repo = PendingRepairRepo(db)
    pending = await pending_repo.list_pending_by_writing_run(run_id)
    return ApiResponse.success(data=[PendingRepairOut.model_validate(p).model_dump() for p in pending])


@router.put("/writing/repairs/{repair_id}/resolve")
async def resolve_repair(
    novel_id: int,
    repair_id: int,
    body: ResolveRepairRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RepairService(db=db, user_id=current_user.id, novel_id=novel_id)
    result = await svc.resolve(
        novel_id=novel_id,
        repair_id=repair_id,
        action=body.action,
        choice_index=body.choice_index,
        intent_text=body.intent_text,
    )
    data = {"pending_repair": PendingRepairOut.model_validate(result["pending_repair"]).model_dump()}
    if result.get("draft_revision"):
        from app.schemas.plot_planning import DraftRevisionOut
        data["draft_revision"] = DraftRevisionOut.model_validate(result["draft_revision"]).model_dump()
    else:
        data["draft_revision"] = None
    return ApiResponse.success(data=data)


@router.post("/writing-runs/{run_id}/review")
async def review_writing_run(
    novel_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    result = await svc.review_writing_run(run_id)
    return ApiResponse.success(data=result)
