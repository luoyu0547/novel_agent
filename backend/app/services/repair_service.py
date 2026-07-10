from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.writer import BaseWritingGenerator, DeepSeekWritingGenerator
from app.core.exceptions import NotFound, AppException
from app.models.novel import Novel
from app.models.writing import WritingRun, PendingRepair
from app.repositories.quality_gate_repo import PendingRepairRepo, RepairLogRepo


class RepairService:
    def __init__(
        self,
        db: AsyncSession,
        user_id: int,
        novel_id: int,
        generator: Optional[BaseWritingGenerator] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.generator = generator or DeepSeekWritingGenerator()

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
    ) -> PendingRepair:
        await self._ensure_owned_novel()

        pending_repo = PendingRepairRepo(self.db)
        repair = await pending_repo.get_by_id(repair_id)
        if not repair or repair.novel_id != novel_id:
            raise NotFound("修复项不存在")
        if repair.status != "pending":
            raise AppException("该修复项已处理")

        if action == "dismiss":
            result = await pending_repo.update_status(repair_id, "dismissed")
        elif action == "apply":
            intent = intent_text
            if repair.intent_type == "choice" and choice_index is not None and repair.options:
                choices = repair.options
                if 0 <= choice_index < len(choices):
                    choice = choices[choice_index]
                    intent = f"{choice.get('label', '')}: {choice.get('summary', '')}"

            run = await self.db.get(WritingRun, repair.writing_run_id)
            if not run:
                raise NotFound("写作运行不存在")

            old_text_arg = repair.location
            new_draft = await self.generator.rewrite_fragment(
                draft=run.draft_content,
                location=repair.location,
                context=repair.context,
                intent=intent,
            )

            old_text, new_text = self._extract_replacement(
                run.draft_content, new_draft, repair.location
            )

            run.draft_content = new_draft
            await self.db.flush()

            log_repo = RepairLogRepo(self.db)
            await log_repo.create(novel_id, repair.writing_run_id, {
                "issue_type": repair.issue_type,
                "description": repair.description,
                "location": repair.location,
                "old_text": old_text,
                "new_text": new_text,
            })

            result = await pending_repo.update_status(repair_id, "applied")
        else:
            raise AppException(f"不支持的动作: {action}")

        remaining = await pending_repo.list_pending_by_writing_run(repair.writing_run_id)
        if not remaining:
            run = await self.db.get(WritingRun, repair.writing_run_id)
            if run:
                run.has_pending_repairs = False

        await self.db.commit()
        return result

    @staticmethod
    def _extract_replacement(old_draft: str, new_draft: str, location: str) -> tuple[str, str]:
        pos = old_draft.find(location)
        if pos < 0:
            return location, location
        old_text = old_draft[pos:pos + len(location)]
        suffix = old_draft[pos + len(location):]
        new_end = new_draft.find(suffix, pos)
        if new_end >= 0:
            new_text = new_draft[pos:new_end]
        else:
            new_text = new_draft[pos:pos + len(location)]
        return old_text, new_text
