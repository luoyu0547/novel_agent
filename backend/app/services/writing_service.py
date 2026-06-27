"""写作业务逻辑。可通过 generator 参数注入 fake generator 用于测试。"""

import json
import datetime
import logging
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.writer import BaseWritingGenerator, DeepSeekWritingGenerator
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
    ):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.generator = generator or DeepSeekWritingGenerator()
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
        return await self.blueprint_repo.create(self.novel_id, {"content_json": content, "status": "draft"})

    async def update_blueprint(self, blueprint_id: int, data: dict) -> NovelBlueprint:
        await self._ensure_owned_novel()
        blueprint = await self.blueprint_repo.get_by_id(blueprint_id)
        if not blueprint or blueprint.novel_id != self.novel_id:
            raise NotFound("蓝图不存在")
        return await self.blueprint_repo.update(blueprint, data)

    async def activate_blueprint(self, blueprint_id: int) -> NovelBlueprint:
        await self._ensure_owned_novel()
        blueprint = await self.blueprint_repo.get_by_id(blueprint_id)
        if not blueprint or blueprint.novel_id != self.novel_id:
            raise NotFound("蓝图不存在")
        if blueprint.status == "archived":
            raise AppException("已归档的蓝图无法激活")
        await self.blueprint_repo.deactivate_all(self.novel_id)
        return await self.blueprint_repo.update(blueprint, {"status": "active"})

    # ---- Chapter Plan ----

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
        return await self.plan_repo.create(self.novel_id, {"content_json": content, "position": position, "status": "ready"})

    async def update_chapter_plan(self, plan_id: int, data: dict) -> ChapterPlan:
        await self._ensure_owned_novel()
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan or plan.novel_id != self.novel_id:
            raise NotFound("章节计划不存在")
        return await self.plan_repo.update(plan, data)

    # ---- Chapter Brief ----

    async def generate_chapter_brief(self, plan_id: int) -> ChapterBrief:
        novel = await self._ensure_owned_novel()
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan or plan.novel_id != self.novel_id:
            raise NotFound("章节计划不存在")
        blueprint = await self.blueprint_repo.get_active(self.novel_id)
        blueprint_data = blueprint.content_json if blueprint else {}
        brief_content = await self.generator.generate_chapter_brief(plan.content_json, blueprint_data, DEFAULT_LENGTH_CONTRACT)
        return await self.brief_repo.create(self.novel_id, {
            "chapter_plan_id": plan_id,
            "brief_json": brief_content,
            "length_contract_json": dict(DEFAULT_LENGTH_CONTRACT),
            "status": "ready",
        })

    async def update_chapter_brief(self, brief_id: int, data: dict) -> ChapterBrief:
        await self._ensure_owned_novel()
        brief = await self.brief_repo.get_by_id(brief_id)
        if not brief or brief.novel_id != self.novel_id:
            raise NotFound("章节任务书不存在")
        return await self.brief_repo.update(brief, data)

    # ---- Context Package ----

    async def generate_context_package(self, brief_id: int) -> ContextPackage:
        novel = await self._ensure_owned_novel()
        brief = await self.brief_repo.get_by_id(brief_id)
        if not brief or brief.novel_id != self.novel_id:
            raise NotFound("章节任务书不存在")
        orchestrated = await self._build_context_package(novel, brief)
        return await self.context_repo.create(self.novel_id, {
            "chapter_brief_id": brief_id,
            "package_json": orchestrated,
        })

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

    async def create_writing_run(self, brief_id: int) -> WritingRun:
        novel = await self._ensure_owned_novel()
        brief = await self.brief_repo.get_by_id(brief_id)
        if not brief or brief.novel_id != self.novel_id:
            raise NotFound("章节任务书不存在")
        package = await self._build_context_package(novel, brief)
        context_package = await self.context_repo.create(self.novel_id, {"chapter_brief_id": brief_id, "package_json": package})
        run = await self.run_repo.create(self.novel_id, {
            "chapter_brief_id": brief_id,
            "context_package_id": context_package.id,
            "status": "running",
        })
        try:
            draft = await self.generator.generate_draft(package)
            word_count = self._count_words(draft)
            gate_result = self._check_gate(draft, word_count, brief.length_contract_json)
            if not gate_result["passed"]:
                draft = await self.generator.generate_draft(package)
                word_count = self._count_words(draft)
                gate_result = self._check_gate(draft, word_count, brief.length_contract_json)
            run = await self.run_repo.update(run, {
                "draft_content": draft,
                "word_count": word_count,
                "gate_result_json": gate_result,
                "status": "completed",
            })
        except Exception as e:
            logger.exception("WritingRun failed")
            run = await self.run_repo.update(run, {
                "status": "failed",
                "error_message": str(e),
            })
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
            await self.db.commit()
            run.target_chapter_id = chapter.id
        run.status = "accepted"
        run.accepted_at = datetime.datetime.now()
        await self.db.commit()
        return chapter

    async def discard_writing_run(self, run_id: int):
        await self._ensure_owned_novel()
        run = await self.run_repo.get_by_id(run_id)
        if not run or run.novel_id != self.novel_id:
            raise NotFound("写作运行不存在")
        if run.status in ("accepted", "discarded"):
            raise AppException("该写作运行已处理")
        await self.run_repo.update(run, {"status": "discarded"})

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
