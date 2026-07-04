import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.quality_gate import BaseQualityGateAgent, FakeQualityGateAgent
from app.models.writing import WritingRun
from app.repositories.quality_gate_repo import RepairLogRepo, PendingRepairRepo

logger = logging.getLogger("novel_agent.quality_gate")


class QualityGateService:
    def __init__(
        self,
        db: AsyncSession,
        agent: BaseQualityGateAgent | None = None,
    ):
        self.db = db
        self.agent = agent or FakeQualityGateAgent()
        self.log_repo = RepairLogRepo(db)
        self.pending_repo = PendingRepairRepo(db)

    async def run(self, run: WritingRun, brief: dict, context_package: dict) -> dict:
        try:
            results = await self.agent.check(run.draft_content, brief, context_package)
        except Exception as e:
            logger.exception("Quality gate check failed, skipping")
            return {"gated": False, "has_pending_repairs": False, "rewrite_needed": False}

        has_pending = False
        auto_rewrite_needed = False

        for r in results:
            if r.passed:
                continue
            if r.severity == "auto_fixable":
                if r.fix_strategy == "full_rewrite":
                    auto_rewrite_needed = True
                    await self.log_repo.create(run.novel_id, run.id, {
                        "issue_type": r.issue_type,
                        "description": r.fix_description or f"自动修复({r.issue_type})",
                        "location": r.location,
                        "old_text": "",
                        "new_text": "",
                    })
                elif r.fix_strategy == "local_replace" and r.fixed_text:
                    new_draft = run.draft_content.replace(r.location, r.fixed_text)
                    old_snippet = r.location[:100]
                    new_snippet = r.fixed_text[:100]
                    await self.log_repo.create(run.novel_id, run.id, {
                        "issue_type": r.issue_type,
                        "description": r.fix_description or f"局部替换({r.issue_type})",
                        "location": r.location[:200],
                        "old_text": old_snippet,
                        "new_text": new_snippet,
                    })
                    run.draft_content = new_draft
            elif r.severity == "needs_intent":
                has_pending = True
                await self.pending_repo.create(run.novel_id, run.target_chapter_id or 0, run.id, {
                    "issue_type": r.issue_type,
                    "description": r.description,
                    "location": r.location,
                    "context": r.context,
                    "options": r.options,
                    "intent_type": r.intent_type or "freeform",
                })

        run.gated = True
        run.has_pending_repairs = has_pending

        await self.db.flush()
        return {"gated": True, "has_pending_repairs": has_pending, "rewrite_needed": auto_rewrite_needed}
