"""Phase 4 辅助修订 API 路由。

暴露 DraftVersion 生命周期、审阅问题修复、候选修订应用/拒绝等端点。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.revision import (
    ApplyRevisionRequest,
    CreateDraftVersionRequest,
    CreateRevisionRequest,
    DraftRevisionOut,
    DraftVersionOut,
    IgnoreIssueRequest,
    ManualRevisionRequest,
    RepairOptionOut,
    RestoreVersionRequest,
    ReviewIssueOut,
)
from app.services.draft_version_service import DraftVersionService
from app.services.modification_service import ModificationService

router = APIRouter(prefix="/novels/{novel_id}", tags=["Revisions"])


# ── Dependency providers ─────────────────────────────────────────────


def get_draft_version_service(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DraftVersionService:
    return DraftVersionService(db, current_user.id, novel_id)


def get_modification_service(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ModificationService:
    return ModificationService(db, current_user.id, novel_id)


# Type aliases for injected dependencies
DraftVersionSvc = Annotated[DraftVersionService, Depends(get_draft_version_service)]
ModificationSvc = Annotated[ModificationService, Depends(get_modification_service)]


# ── DraftVersion endpoints ──────────────────────────────────────────


@router.get("/writing-runs/{run_id}/draft-versions")
async def list_draft_versions(
    run_id: int,
    svc: DraftVersionSvc,
):
    versions = await svc.list_versions(run_id)
    return ApiResponse.success(
        data=[DraftVersionOut.model_validate(v).model_dump() for v in versions]
    )


@router.get("/draft-versions/{version_id}")
async def get_draft_version(
    version_id: int,
    svc: DraftVersionSvc,
):
    version = await svc.get_version(version_id)
    return ApiResponse.success(data=DraftVersionOut.model_validate(version).model_dump())


@router.post("/writing-runs/{run_id}/draft-versions")
async def create_draft_version(
    run_id: int,
    body: CreateDraftVersionRequest,
    svc: DraftVersionSvc,
):
    version = await svc.create_new_version(
        run_id, body.based_on_version_id, body.change_reason
    )
    return ApiResponse.success(data=DraftVersionOut.model_validate(version).model_dump())


@router.post("/draft-versions/{version_id}/restore-into-current")
async def restore_version_into_current(
    version_id: int,
    body: RestoreVersionRequest,
    svc: DraftVersionSvc,
):
    version, revision = await svc.restore_into_current(
        version_id, body.base_revision_sequence, body.change_reason
    )
    return ApiResponse.success(
        data={
            "version": DraftVersionOut.model_validate(version).model_dump(),
            "revision": DraftRevisionOut.model_validate(revision).model_dump(),
        }
    )


@router.post("/writing-runs/{run_id}/manual-revisions")
async def create_manual_revision(
    run_id: int,
    body: ManualRevisionRequest,
    svc: DraftVersionSvc,
):
    version, revision = await svc.save_manual_revision(
        run_id, body.content, body.change_reason, body.base_revision_sequence
    )
    return ApiResponse.success(
        data={
            "version": DraftVersionOut.model_validate(version).model_dump(),
            "revision": DraftRevisionOut.model_validate(revision).model_dump(),
        }
    )


# ── ReviewIssue endpoints ───────────────────────────────────────────


@router.get("/writing-runs/{run_id}/review-issues")
async def list_review_issues(
    run_id: int,
    dv_svc: DraftVersionSvc,
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.quality_gate_repo import ReviewIssueRepo

    # Verify ownership via _get_owned_run
    await dv_svc._get_owned_run(run_id)

    issue_repo = ReviewIssueRepo(db)
    issues = await issue_repo.list_by_writing_run(run_id)
    return ApiResponse.success(
        data=[ReviewIssueOut.model_validate(i).model_dump() for i in issues]
    )


@router.post("/review-issues/{issue_id}/repair-options")
async def generate_repair_options(
    issue_id: int,
    svc: ModificationSvc,
):
    options = await svc.generate_options(issue_id)
    return ApiResponse.success(
        data=[
            RepairOptionOut(
                option_index=i,
                label=opt.label,
                description=opt.summary,
            ).model_dump()
            for i, opt in enumerate(options)
        ]
    )


@router.post("/review-issues/{issue_id}/draft-revisions")
async def create_issue_revision(
    issue_id: int,
    body: CreateRevisionRequest,
    svc: ModificationSvc,
):
    revision = await svc.create_revision(
        issue_id, option_index=body.option_index, custom_intent=body.custom_intent
    )
    return ApiResponse.success(data=DraftRevisionOut.model_validate(revision).model_dump())


@router.put("/review-issues/{issue_id}/ignore")
async def ignore_review_issue(
    issue_id: int,
    body: IgnoreIssueRequest,
    svc: ModificationSvc,
):
    issue = await svc.ignore_issue(issue_id, body.reason)
    return ApiResponse.success(data=ReviewIssueOut.model_validate(issue).model_dump())


# ── DraftRevision endpoints ─────────────────────────────────────────


@router.get("/draft-versions/{version_id}/draft-revisions")
async def list_draft_revisions(
    version_id: int,
    dv_svc: DraftVersionSvc,
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.draft_version_repo import DraftVersionRepo

    # Verify the version exists and belongs to the novel
    await dv_svc.get_version(version_id)

    repo = DraftVersionRepo(db)
    revisions = await repo.list_revisions(version_id)
    return ApiResponse.success(
        data=[DraftRevisionOut.model_validate(r).model_dump() for r in revisions]
    )


@router.put("/draft-revisions/{revision_id}/apply")
async def apply_draft_revision(
    revision_id: int,
    svc: DraftVersionSvc,
    body: ApplyRevisionRequest | None = None,
):
    req = body or ApplyRevisionRequest()
    version, revision = await svc.apply_revision(
        revision_id, confirm_expanded_scope=req.confirm_expanded_scope
    )
    return ApiResponse.success(
        data={
            "version": DraftVersionOut.model_validate(version).model_dump(),
            "revision": DraftRevisionOut.model_validate(revision).model_dump(),
        }
    )


@router.put("/draft-revisions/{revision_id}/reject")
async def reject_draft_revision(
    revision_id: int,
    svc: DraftVersionSvc,
):
    revision = await svc.reject_revision(revision_id)
    return ApiResponse.success(data=DraftRevisionOut.model_validate(revision).model_dump())
