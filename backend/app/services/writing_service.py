"""写作业务逻辑。可通过 generator 参数注入 fake generator 用于测试。"""

import json
import datetime
import logging
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.quality_gate import BaseQualityGateAgent, FakeQualityGateAgent, DeepSeekQualityGateAgent
from app.ai.service import BaseExtractionService, DeepSeekExtractionService
from app.ai.writer import BaseWritingGenerator, DeepSeekWritingGenerator
from app.services.quality_gate_service import QualityGateService
from app.core.exceptions import NotFound, AppException
from app.models.novel import Novel, Chapter
from app.models.writing import NovelBlueprint, ChapterPlan, ChapterBrief, ContextPackage, WritingRun
from app.repositories.novel_repo import NovelRepo
from app.repositories.writing_repo import (
    BlueprintRepo,
    ChapterPlanRepo,
    ChapterBriefRepo,
    ContextPackageRepo,
    WritingRunRepo,
)

logger = logging.getLogger("novel_agent.writing")


DEFAULT_LENGTH_CONTRACT = {
    "target_words": 3000,
    "min_words": 2000,
    "max_words": 5000,
    "scene_word_allocation": [],
    "density_requirements": "字数增长必须来自有效场景、动作、心理、对话和细节，而非重复说明",
    "expansion_strategy": "优先扩写任务书中指定的场景过程、角色反应、冲突升级和信息铺垫",
    "compression_strategy": "优先压缩重复说明、空泛心理描写和无关闲聊",
}


class WritingService:
    def __init__(
        self,
        db: AsyncSession,
        user_id: int,
        novel_id: int,
        generator: Optional[BaseWritingGenerator] = None,
        gate_agent: Optional[BaseQualityGateAgent] = None,
        extraction_service: Optional[BaseExtractionService] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.generator = generator or DeepSeekWritingGenerator()
        self.gate_agent = gate_agent or DeepSeekQualityGateAgent()
        self.extraction_service = extraction_service or DeepSeekExtractionService()
        self.novel_repo = NovelRepo(db)
        self.blueprint_repo = BlueprintRepo(db)
        self.plan_repo = ChapterPlanRepo(db)
        self.brief_repo = ChapterBriefRepo(db)
        self.context_repo = ContextPackageRepo(db)
        self.run_repo = WritingRunRepo(db)

    async def _ensure_owned_novel(self) -> Novel:
        result = await self.db.execute(
            select(Novel)
            .where(Novel.id == self.novel_id)
            .options(
                selectinload(Novel.chapters),
                selectinload(Novel.characters),
                selectinload(Novel.world_settings),
            )
        )
        novel = result.scalar_one_or_none()
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != self.user_id:
            raise NotFound("小说不存在")
        return novel

    # ---- Blueprint ----

    async def get_blueprints(self) -> list:
        await self._ensure_owned_novel()
        return await self.blueprint_repo.list_by_novel(self.novel_id)

    async def generate_blueprint(self, author_input: str) -> NovelBlueprint:
        novel = await self._ensure_owned_novel()
        novel_data = {"title": novel.title, "description": novel.description, "genre": novel.genre, "style_guide": novel.style_guide}
        content = await self.generator.generate_blueprint(novel_data, author_input)
        result = await self.blueprint_repo.create(self.novel_id, {"content_json": content, "status": "draft"})
        await self.db.commit()
        return result

    async def update_blueprint(self, blueprint_id: int, data: dict) -> NovelBlueprint:
        await self._ensure_owned_novel()
        blueprint = await self.blueprint_repo.get_by_id(blueprint_id)
        if not blueprint or blueprint.novel_id != self.novel_id:
            raise NotFound("蓝图不存在")
        result = await self.blueprint_repo.update(blueprint, data)
        await self.db.commit()
        return result

    async def activate_blueprint(self, blueprint_id: int) -> NovelBlueprint:
        await self._ensure_owned_novel()
        blueprint = await self.blueprint_repo.get_by_id(blueprint_id)
        if not blueprint or blueprint.novel_id != self.novel_id:
            raise NotFound("蓝图不存在")
        if blueprint.status == "archived":
            raise AppException("已归档的蓝图无法激活")
        await self.blueprint_repo.deactivate_all(self.novel_id)
        result = await self.blueprint_repo.update(blueprint, {"status": "active"})
        await self.db.commit()
        return result

    # ---- Chapter Plan ----

    async def get_chapter_plans(self, active_only: bool = False) -> list[ChapterPlan]:
        await self._ensure_owned_novel()
        return await self.plan_repo.list_by_novel(self.novel_id, active_only=active_only)

    async def get_chapter_plan(self, plan_id: int) -> ChapterPlan:
        await self._ensure_owned_novel()
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan or plan.novel_id != self.novel_id:
            raise NotFound("章节计划不存在")
        return plan

    async def generate_chapter_plan(self) -> ChapterPlan:
        novel = await self._ensure_owned_novel()
        blueprint = await self.blueprint_repo.get_active(self.novel_id)
        if not blueprint:
            raise AppException("请先生成并激活小说蓝图")
        chapters = []
        if novel.chapters:
            chapters = [{"id": c.id, "title": c.title, "summary": c.summary} for c in novel.chapters]
        novel_data = {"chapters": chapters}
        content = await self.generator.generate_chapter_plan(blueprint.content_json, novel_data)
        position = (len(chapters) or 0) + 1
        result = await self.plan_repo.create(self.novel_id, {
            "content_json": content,
            "position": position,
            "status": "ready",
            "blueprint_id": blueprint.id,
            "version": 1,
        })
        await self.db.commit()
        return result

    async def generate_chapter_plans_batch(self, volume_arc_id: int, count: int) -> list[ChapterPlan]:
        novel = await self._ensure_owned_novel()
        blueprint = await self.blueprint_repo.get_active(self.novel_id)
        if not blueprint:
            raise AppException("请先生成并激活小说蓝图")

        from app.models.planning import VolumeArc
        arc = await self.db.get(VolumeArc, volume_arc_id)
        if not arc or arc.novel_id != self.novel_id:
            raise NotFound("卷弧不存在")
        if arc.status == "archived":
            raise AppException("已归档的卷弧不能生成章节计划")

        chapters = []
        if novel.chapters:
            chapters = [{"id": c.id, "title": c.title, "summary": c.summary} for c in novel.chapters]
        novel_data = {"chapters": chapters}

        contents = await self.generator.generate_chapter_plans_batch(blueprint.content_json, novel_data, count)
        if not isinstance(contents, list):
            contents = [contents]

        created = []
        base_position = (len(chapters) or 0) + 1
        for i, content in enumerate(contents):
            plan = ChapterPlan(
                novel_id=self.novel_id,
                blueprint_id=blueprint.id,
                volume_arc_id=volume_arc_id,
                position=base_position + i,
                status="ready",
                content_json=content if isinstance(content, dict) else {},
                version=1,
            )
            self.db.add(plan)
            created.append(plan)
        await self.db.flush()
        await self.db.commit()
        return created

    async def update_chapter_plan(self, plan_id: int, data: dict) -> ChapterPlan:
        await self._ensure_owned_novel()
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan or plan.novel_id != self.novel_id:
            raise NotFound("章节计划不存在")
        result = await self.plan_repo.update(plan, data)
        await self.db.commit()
        return result

    # ---- Chapter Brief ----

    async def generate_chapter_brief(self, plan_id: int) -> ChapterBrief:
        novel = await self._ensure_owned_novel()
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan or plan.novel_id != self.novel_id:
            raise NotFound("章节计划不存在")
        blueprint = await self.blueprint_repo.get_active(self.novel_id)
        blueprint_data = blueprint.content_json if blueprint else {}
        brief_content = await self.generator.generate_chapter_brief(plan.content_json, blueprint_data, DEFAULT_LENGTH_CONTRACT)
        result = await self.brief_repo.create(self.novel_id, {
            "chapter_plan_id": plan_id,
            "brief_json": brief_content,
            "length_contract_json": dict(DEFAULT_LENGTH_CONTRACT),
            "status": "ready",
        })
        await self.db.commit()
        return result

    async def update_chapter_brief(self, brief_id: int, data: dict) -> ChapterBrief:
        await self._ensure_owned_novel()
        brief = await self.brief_repo.get_by_id(brief_id)
        if not brief or brief.novel_id != self.novel_id:
            raise NotFound("章节任务书不存在")
        result = await self.brief_repo.update(brief, data)
        await self.db.commit()
        return result

    # ---- Context Package ----

    async def generate_context_package(self, brief_id: int) -> ContextPackage:
        novel = await self._ensure_owned_novel()
        brief = await self.brief_repo.get_by_id(brief_id)
        if not brief or brief.novel_id != self.novel_id:
            raise NotFound("章节任务书不存在")
        orchestrated = await self._build_context_package(novel, brief)
        result = await self.context_repo.create(self.novel_id, {
            "chapter_brief_id": brief_id,
            "package_json": orchestrated,
        })
        await self.db.commit()
        return result

    async def _build_context_package(self, novel: Novel, brief: ChapterBrief) -> dict:
        chapters = novel.chapters or []
        previous_chapter = chapters[-1] if chapters else None
        package = {
            "blueprint_summary": "",
            "chapter_brief": brief.brief_json,
            "length_contract": brief.length_contract_json,
            "acceptance_criteria": brief.brief_json.get("acceptance_criteria", ""),
            "previous_chapter_summary": previous_chapter.summary if previous_chapter else None,
            "characters": [],
            "world_settings": [],
            "plot_facts": [],
            "foreshadowings": [],
            "style_guide": novel.style_guide or "",
        }
        blueprint = await self.blueprint_repo.get_active(self.novel_id)
        if blueprint:
            package["blueprint_summary"] = json.dumps(blueprint.content_json, ensure_ascii=False)
        if novel.characters:
            package["characters"] = [
                {"name": c.name, "story_role": c.story_role, "identity": c.identity, "personality": c.personality, "current_state": c.current_state}
                for c in novel.characters
            ]
        if novel.world_settings:
            package["world_settings"] = [
                {"title": ws.title, "category": ws.category, "content": ws.content}
                for ws in novel.world_settings
            ]
        return package

    # ---- Writing Run ----

    async def create_writing_run(self, brief_id: int, context_package_id: Optional[int] = None) -> WritingRun:
        novel = await self._ensure_owned_novel()
        brief = await self.brief_repo.get_by_id(brief_id)
        if not brief or brief.novel_id != self.novel_id:
            raise NotFound("章节任务书不存在")

        # Reject archived chapter plans
        plan = await self.plan_repo.get_by_id(brief.chapter_plan_id)
        if plan and plan.status == "archived":
            raise AppException("已归档的章节计划不能用于生成草稿")
        if plan and plan.novel_id != self.novel_id:
            raise NotFound("章节计划不存在")

        if context_package_id:
            context_package = await self.context_repo.get_by_id(context_package_id)
            if not context_package or context_package.novel_id != self.novel_id:
                raise NotFound("上下文包不存在")
            package = context_package.package_json
        else:
            package = await self._build_context_package(novel, brief)
            context_package = await self.context_repo.create(self.novel_id, {"chapter_brief_id": brief_id, "package_json": package})

        # Capture input snapshot for planning versions
        blueprint = await self.blueprint_repo.get_active(self.novel_id)
        input_snapshot = {
            "blueprint_id": blueprint.id if blueprint else None,
            "blueprint_version": blueprint.version if blueprint else None,
            "chapter_plan_id": brief.chapter_plan_id if brief else None,
            "chapter_plan_version": plan.version if plan else None,
        }
        plan_version_ids: list[int] = []
        if blueprint and blueprint.id:
            plan_version_ids.append(blueprint.id)
        if plan and plan.id:
            plan_version_ids.append(plan.id)

        run = await self.run_repo.create(self.novel_id, {
            "chapter_brief_id": brief_id,
            "context_package_id": context_package.id,
            "status": "running",
            "input_snapshot": input_snapshot,
            "plan_version_ids": plan_version_ids,
        })
        try:
            draft = await self.generator.generate_draft(package)
            word_count = self._count_words(draft)
            gate_result = self._check_gate(draft, word_count, brief.length_contract_json)
            if not gate_result["passed"]:
                package_with_hint = dict(package)
                hints = []
                if word_count < brief.length_contract_json.get("min_words", 2000):
                    hints.append("草稿字数不足，请扩写场景过程、角色反应和冲突升级")
                if gate_result.get("outline_like"):
                    hints.append("草稿像大纲，请写出完整正文")
                if hints:
                    package_with_hint["expansion_hint"] = "；".join(hints)
                draft = await self.generator.generate_draft(package_with_hint)
                word_count = self._count_words(draft)
                gate_result = self._check_gate(draft, word_count, brief.length_contract_json)

            # --- Quality Gate (with auto-fix retry loop, max 3 iterations) ---
            run.draft_content = draft
            run.word_count = word_count
            run.gate_result_json = gate_result
            gate_svc = QualityGateService(db=self.db, agent=self.gate_agent)
            gate_svc_result = {
                "gated": False,
                "has_pending_repairs": False,
                "rewrite_needed": False,
                "snapshot": gate_result,
            }
            max_iterations = 3
            for retry in range(max_iterations):
                gate_svc_result = await gate_svc.run(run, brief.brief_json, package)
                run.gate_result_json = gate_svc_result.get("snapshot", run.gate_result_json)
                if not gate_svc_result.get("rewrite_needed"):
                    break
                # Regenerate for the next gate check, unless this is the last
                # allowed iteration (stop after 3 gate checks / 2 rewrites).
                if retry < max_iterations - 1:
                    feedback = await self._collect_gate_feedback(run.id)
                    package_with_feedback = dict(package)
                    package_with_feedback["gate_feedback"] = feedback
                    await self._cleanup_gate_records(run.id)
                    draft = await self.generator.generate_draft(package_with_feedback)
                    word_count = self._count_words(draft)
                    run.draft_content = draft
                    run.word_count = word_count
            # ---

            run = await self.run_repo.update(run, {
                "draft_content": draft,
                "word_count": word_count,
                "gate_result_json": gate_svc_result.get("snapshot", gate_result),
                "gated": gate_svc_result.get("gated", False),
                "has_pending_repairs": gate_svc_result.get("has_pending_repairs", False),
                "status": "completed",
            })
        except Exception as e:
            logger.exception("WritingRun failed")
            run = await self.run_repo.update(run, {
                "status": "failed",
                "error_message": str(e),
            })
        await self.db.commit()
        return run

    async def get_writing_runs(self) -> list:
        await self._ensure_owned_novel()
        return await self.run_repo.list_by_novel(self.novel_id)

    async def get_writing_run(self, run_id: int) -> WritingRun:
        await self._ensure_owned_novel()
        run = await self.run_repo.get_by_id(run_id)
        if not run or run.novel_id != self.novel_id:
            raise NotFound("写作运行不存在")
        return run

    async def get_writing_run_with_repairs(self, run_id: int) -> dict:
        run = await self.get_writing_run(run_id)
        from app.repositories.quality_gate_repo import RepairLogRepo, PendingRepairRepo
        log_repo = RepairLogRepo(self.db)
        pending_repo = PendingRepairRepo(self.db)
        logs = await log_repo.list_by_writing_run(run_id)
        pending = await pending_repo.list_by_writing_run(run_id)
        return {"run": run, "repair_logs": logs, "pending_repairs": pending}

    async def accept_writing_run(self, run_id: int):
        """接受草稿，写入章节正文或创建新章节。"""
        await self._ensure_owned_novel()
        run = await self.run_repo.get_by_id(run_id)
        if not run or run.novel_id != self.novel_id:
            raise NotFound("写作运行不存在")
        if run.status in ("accepted", "discarded"):
            raise AppException("该写作运行已处理")
        if run.status != "completed":
            raise AppException("只能接受已完成的写作运行")
        if run.target_chapter_id:
            stmt = select(Chapter).where(Chapter.id == run.target_chapter_id)
            result = await self.db.execute(stmt)
            chapter = result.scalar_one_or_none()
            if not chapter:
                raise NotFound("目标章节不存在")
            chapter.content = run.draft_content
        else:
            brief = await self.brief_repo.get_by_id(run.chapter_brief_id)
            plan = await self.plan_repo.get_by_id(brief.chapter_plan_id) if brief else None
            title = plan.content_json.get("chapter_title", "新章节") if plan else "新章节"
            chapter = Chapter(
                novel_id=self.novel_id,
                title=title,
                content=run.draft_content,
                summary="",
                status="draft",
            )
            self.db.add(chapter)
            await self.db.flush()
            run.target_chapter_id = chapter.id
        run.status = "accepted"
        run.accepted_at = datetime.datetime.now()
        await self.db.commit()

        extraction_result = {"pending_ids": [], "pending_count": 0, "error": None}
        try:
            extraction_result = await self.extraction_service.extract(
                novel_id=self.novel_id,
                chapter_id=chapter.id,
                user_id=self.user_id,
            )
        except Exception as e:
            logger.exception("Extraction after accept failed for run %s", run_id)
            extraction_result = {"pending_ids": [], "pending_count": 0, "error": str(e)}

        return chapter, extraction_result

    async def discard_writing_run(self, run_id: int):
        await self._ensure_owned_novel()
        run = await self.run_repo.get_by_id(run_id)
        if not run or run.novel_id != self.novel_id:
            raise NotFound("写作运行不存在")
        if run.status in ("accepted", "discarded"):
            raise AppException("该写作运行已处理")
        await self.run_repo.update(run, {"status": "discarded"})
        await self.db.commit()

    # ---- Helpers ----

    def _count_words(self, text: str) -> int:
        return len(re.sub(r"\s+", "", text))

    def _check_gate(self, draft: str, word_count: int, contract: dict) -> dict:
        min_words = contract.get("min_words", 2000)
        target_words = contract.get("target_words", 3000)
        max_words = contract.get("max_words", 5000)
        reasons = []
        outline_like = self._is_outline_like(draft)
        if word_count < min_words:
            reasons.append(f"字数不足：{word_count}/{min_words}")
        if outline_like:
            reasons.append("正文看起来像大纲或列表")
        passed = len(reasons) == 0
        return {
            "passed": passed,
            "reasons": reasons,
            "min_words": min_words,
            "target_words": target_words,
            "max_words": max_words,
            "outline_like": outline_like,
        }

    def _is_outline_like(self, text: str) -> bool:
        lines = text.strip().split("\n")
        if not lines:
            return False
        marker_lines = sum(1 for l in lines if l.strip().startswith(("- ", "* ", "1.", "场景", "步骤")))
        ratio = marker_lines / len(lines)
        return ratio > 0.3

    async def _collect_gate_feedback(self, run_id: int) -> str:
        """Collect RepairLog descriptions from the current run as feedback text."""
        from app.repositories.quality_gate_repo import RepairLogRepo
        log_repo = RepairLogRepo(self.db)
        logs = await log_repo.list_by_writing_run(run_id)
        return "；".join(l.description for l in logs if l.description)

    async def _cleanup_gate_records(self, run_id: int):
        """Remove RepairLog, PendingRepair and ReviewIssue rows so the next
        iteration starts without stale records from previous rewrites."""
        from app.repositories.quality_gate_repo import RepairLogRepo, PendingRepairRepo, ReviewIssueRepo
        await RepairLogRepo(self.db).cleanup_by_writing_run(run_id)
        await PendingRepairRepo(self.db).cleanup_by_writing_run(run_id)
        await ReviewIssueRepo(self.db).cleanup_by_writing_run(run_id)
