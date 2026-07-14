from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.modification import BaseModificationAgent, DeepSeekModificationAgent
from app.core.exceptions import NotFound, AppException
from app.models.novel import Novel
from app.models.plot_planning import DraftRevision
from app.models.writing import WritingRun, PendingRepair
from app.repositories.quality_gate_repo import PendingRepairRepo, RepairLogRepo
from app.services.modification_service import ModificationService


class RepairService:
    def __init__(
        self,
        db: AsyncSession,
        user_id: int,
        novel_id: int,
        modification_agent: Optional[BaseModificationAgent] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.modification_agent = modification_agent or DeepSeekModificationAgent()

    async def _ensure_owned_novel(self) -> Novel:
        result = await self.db.execute(
            select(Novel).where(Novel.id == self.novel_id)
        )
        novel = result.scalar_one_or_none()
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != self.user_id:
            raise NotFound("小说不存在")
        return novel

    async def resolve(
        self,
        novel_id: int,
        repair_id: int,
        action: str,
        choice_index: Optional[int] = None,
        intent_text: Optional[str] = None,
    ) -> dict:
        """处理修复项。

        dismiss: 调用 ModificationService.ignore_issue() 标记问题忽略，然后标记 PendingRepair dismissed。
        apply: 调用 ModificationService.create_revision() 创建候选修订，不改变 WritingRun，不标记 PendingRepair applied。

        返回 {"pending_repair": PendingRepair, "draft_revision": DraftRevision | None}
        """
        await self._ensure_owned_novel()

        pending_repo = PendingRepairRepo(self.db)
        repair = await pending_repo.get_by_id(repair_id)
        if not repair or repair.novel_id != novel_id:
            raise NotFound("修复项不存在")
        if repair.status != "pending":
            raise AppException("该修复项已处理")

        draft_revision: Optional[DraftRevision] = None

        if action == "dismiss":
            # Call ModificationService.ignore_issue() with intent_text as reason
            mod_svc = ModificationService(
                self.db, self.user_id, self.novel_id,
                modification_agent=self.modification_agent,
            )
            reason = intent_text or "作者选择忽略"
            if repair.review_issue_id:
                await mod_svc.ignore_issue(repair.review_issue_id, reason)
            result = await pending_repo.update_status(repair_id, "dismissed")
        elif action == "apply":
            # Call ModificationService.create_revision() to create candidate
            if repair.review_issue_id:
                mod_svc = ModificationService(
                    self.db, self.user_id, self.novel_id,
                    modification_agent=self.modification_agent,
                )
                draft_revision = await mod_svc.create_revision(
                    repair.review_issue_id,
                    option_index=choice_index,
                    custom_intent=intent_text,
                )
            else:
                raise AppException("修复项未关联审阅问题，无法生成候选修订")
            # Do NOT alter WritingRun; do NOT mark PendingRepair applied yet
            result = repair
        else:
            raise AppException(f"不支持的动作: {action}")

        # Recompute has_pending_repairs
        remaining = await pending_repo.list_pending_by_writing_run(repair.writing_run_id)
        if not remaining:
            run = await self.db.get(WritingRun, repair.writing_run_id)
            if run:
                run.has_pending_repairs = False

        await self.db.commit()
        return {"pending_repair": result, "draft_revision": draft_revision}
