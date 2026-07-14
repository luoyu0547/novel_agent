import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.quality_gate import BaseQualityGateAgent, FakeQualityGateAgent
from app.models.writing import WritingRun
from app.repositories.quality_gate_repo import RepairLogRepo, PendingRepairRepo, ReviewIssueRepo

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
        self.issue_repo = ReviewIssueRepo(db)

    async def run(self, run: WritingRun, brief: dict, context_package: dict) -> dict:
        try:
            results = await self.agent.check(run.draft_content, brief, context_package)
        except Exception as e:
            logger.exception("Quality gate check failed, skipping")
            run.gated = False
            run.has_pending_repairs = False
            run.gate_result_json = {"passed": False, "gated": False, "error": str(e)}
            await self.db.flush()
            return {
                "gated": False,
                "has_pending_repairs": False,
                "rewrite_needed": False,
                "error": str(e),
                "snapshot": run.gate_result_json,
            }

        has_pending = False
        auto_rewrite_needed = False
        failed = []

        # Counters for snapshot reporting
        severity_counts = {"blocking": 0, "major": 0, "minor": 0}
        resolution_counts = {"auto_fixable": 0, "needs_intent": 0}

        for r in results:
            if r.passed:
                continue
            failed.append(r)
            severity_counts[r.severity] = severity_counts.get(r.severity, 0) + 1
            resolution_counts[r.resolution_mode] = resolution_counts.get(r.resolution_mode, 0) + 1

            # First persist ReviewIssue for every failed check
            issue = await self.issue_repo.create(run.novel_id, run.id, {
                "issue_type": r.issue_type,
                "severity": r.severity,
                "resolution_mode": r.resolution_mode,
                "location": r.location,
                "description": r.description or r.fix_description,
                "related_memory": r.context or None,
                "suggestion": r.fix_description or r.suggestion or "",
                "acceptance_blocking": r.severity == "blocking",
            })

            if r.resolution_mode == "auto_fixable":
                if r.fix_strategy == "full_rewrite":
                    auto_rewrite_needed = True
                    await self.log_repo.create(run.novel_id, run.id, {
                        "issue_type": r.issue_type,
                        "description": r.fix_description or f"自动修复({r.issue_type})",
                        "location": r.location,
                        "old_text": "",
                        "new_text": "",
                    })
                    # full_rewrite issue stays open only when retry budget is exhausted;
                    # the cleanup path removes obsolete issues before the next check
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
                    # Successful internal local_replace marks ReviewIssue resolved
                    # with no DraftRevision (v1 does not yet exist)
                    await self.issue_repo.update(issue, {"status": "resolved"})
            elif r.resolution_mode == "needs_intent":
                has_pending = True
                await self.pending_repo.create(
                    run.novel_id,
                    run.target_chapter_id,  # never the sentinel value 0
                    run.id,
                    {
                        "issue_type": r.issue_type,
                        "description": r.description,
                        "location": r.location,
                        "context": r.context,
                        "options": r.options,
                        "intent_type": r.intent_type or "freeform",
                        "review_issue_id": issue.id,
                    },
                )

        run.gated = True
        run.has_pending_repairs = has_pending
        snapshot = {
            "passed": len(failed) == 0,
            "gated": True,
            "failed_count": len(failed),
            "issue_types": [r.issue_type for r in failed],
            "has_pending_repairs": has_pending,
            "rewrite_needed": auto_rewrite_needed,
            "severity_counts": severity_counts,
            "resolution_counts": resolution_counts,
        }
        run.gate_result_json = snapshot

        await self.db.flush()
        return {
            "gated": True,
            "has_pending_repairs": has_pending,
            "rewrite_needed": auto_rewrite_needed,
            "snapshot": snapshot,
        }
