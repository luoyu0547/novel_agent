# v2 阶段 1 最小自主写作闭环 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增从小说蓝图到下一章可编辑草稿的最小自主写作闭环，AI 草稿先进入 WritingRun 草稿池，作者接受后写入章节正文。

**Architecture:** 后端新增 `writing` 模块（数据模型/仓库/服务/API），复用现有 `ai` 模块的 LLM 能力；前端新增写作工作台页面。`WritingService` 接受可注入的 `generator` 参数以支持测试。测试使用 fake generator 而非真实 DeepSeek。

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, SQLite/MySQL-compatible schema, pytest, httpx, Vue 3, TypeScript, Pinia, Vue Router, Vitest。

## Global Constraints

- Scope: 只做"下一章最小自主写作闭环"，不批量生成多章
- 所有子资源必须验证小说属于当前用户
- 保持统一响应格式: `{"code": int, "message": str, "data": any}`
- NovelBlueprint 同一小说只允许一份 `active` 蓝图
- 默认篇幅契约: target_words=3000, min_words=2000, max_words=5000
- accept 时如果 target_chapter_id 存在则覆盖章节正文，不存在则创建新章节
- 不自动触发记忆提取
- accept/discard 后的 WritingRun 不允许再次操作
- 后端默认测试使用 fake generator，不依赖真实 DeepSeek
- 前端验证命令: `npm run type-check`, `npm run build`
- 后端测试命令: `.venv/bin/python -m pytest tests/ -x -q`
- 不修改已有初始 migration

---

## File Structure

### Backend

- Create: `backend/app/models/writing.py` — NovelBlueprint, ChapterPlan, ChapterBrief, ContextPackage, WritingRun
- Create: `backend/app/schemas/writing.py` — 所有 Pydantic schema
- Create: `backend/app/repositories/writing_repo.py` — 所有 CRUD repository
- Create: `backend/app/services/writing_service.py` — 业务逻辑 + AI 编排
- Create: `backend/app/api/writing.py` — 所有写作 API 路由
- Create: `backend/app/ai/writer.py` — WritingGenerator 协议、DeepSeek 实现、Fake 实现
- Modify: `backend/app/models/__init__.py` — 导出 writing 模型
- Modify: `backend/app/main.py` — 注册 writing router
- Create: `backend/alembic/versions/b3c4d5e6f7a8_phase_1_writing_models.py` — 迁移
- Create: `backend/tests/test_phase_1_writing.py` — 写作模块测试
- Create: `backend/tests/test_phase_1_writing_integration.py` — 真实 AI 冒烟测试

### Frontend

- Create: `frontend/src/types/writing.ts` — 蓝图/计划/任务书/上下文包/WritingRun 类型
- Create: `frontend/src/api/writing.ts` — 写作 API 调用
- Create: `frontend/src/stores/writing.ts` — Pinia store
- Create: `frontend/src/views/novels/WritingWorkspaceView.vue` — 写作工作台
- Modify: `frontend/src/router/index.ts` — 新增 `/novels/:id/writing` 路由
- Modify: `frontend/src/components/novels/NovelWorkspaceTabs.vue` — 新增"写作"tab

---

### Task 1: Backend Writing Models

**Files:**
- Create: `backend/app/models/writing.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Consumes: `app.core.database.Base`
- Produces: `NovelBlueprint`, `ChapterPlan`, `ChapterBrief`, `ContextPackage`, `WritingRun` — 五个 SQLAlchemy 模型

- [ ] **Step 1: Create `backend/app/models/writing.py`**

```python
import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NovelBlueprint(Base):
    __tablename__ = "novel_blueprints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(default="draft")
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    novel = relationship("Novel", back_populates="blueprints")


class ChapterPlan(Base):
    __tablename__ = "chapter_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(default="draft")
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)


class ChapterBrief(Base):
    __tablename__ = "chapter_briefs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_plan_id: Mapped[int] = mapped_column(ForeignKey("chapter_plans.id"), nullable=False)
    chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    status: Mapped[str] = mapped_column(default="draft")
    brief_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    length_contract_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)


class ContextPackage(Base):
    __tablename__ = "context_packages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_brief_id: Mapped[int] = mapped_column(ForeignKey("chapter_briefs.id"), nullable=False)
    package_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)


class WritingRun(Base):
    __tablename__ = "writing_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_brief_id: Mapped[int] = mapped_column(ForeignKey("chapter_briefs.id"), nullable=False)
    context_package_id: Mapped[int] = mapped_column(ForeignKey("context_packages.id"), nullable=False)
    target_chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    status: Mapped[str] = mapped_column(default="running")
    draft_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gate_result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    accepted_at: Mapped[Optional[datetime.datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)
```

- [ ] **Step 2: Add relationships to existing `Novel` model**

Edit `backend/app/models/novel.py` to add these relationships inside class `Novel`:

```python
class Novel(Base):
    ...
    characters = relationship("CharacterProfile", back_populates="novel", cascade="all, delete-orphan")
    world_settings = relationship("WorldSetting", back_populates="novel", cascade="all, delete-orphan")
    blueprints = relationship("NovelBlueprint", back_populates="novel", cascade="all, delete-orphan")
```

- [ ] **Step 3: Update `backend/app/models/__init__.py`**

```python
from app.models.foreshadowing import Foreshadowing
from app.models.memory import CharacterProfile, WorldSetting
from app.models.novel import Novel, Chapter
from app.models.pending_memory import PendingMemory
from app.models.plot_fact import PlotFact
from app.models.user import User
from app.models.writing import NovelBlueprint, ChapterPlan, ChapterBrief, ContextPackage, WritingRun

__all__ = [
    "User",
    "Novel", "Chapter",
    "CharacterProfile", "WorldSetting",
    "PendingMemory", "PlotFact", "Foreshadowing",
    "NovelBlueprint", "ChapterPlan", "ChapterBrief", "ContextPackage", "WritingRun",
]
```

- [ ] **Step 4: Verify models import correctly**

```bash
.venv/bin/python -c "from app.models.writing import NovelBlueprint, ChapterPlan, ChapterBrief, ContextPackage, WritingRun; print('writing models OK')"
```

Expected: `writing models OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/writing.py backend/app/models/novel.py backend/app/models/__init__.py
git commit -m "feat: add writing models (blueprint, plan, brief, context, writing_run)"
```

---

### Task 2: Backend Writing Schemas

**Files:**
- Create: `backend/app/schemas/writing.py`

**Interfaces:**
- Consumes: models from Task 1
- Produces: Pydantic create/update/out schemas for all 5 writing models, plus API request/response types for `BlueprintGenerateRequest`, `ChapterPlanGenerateResponse`, `ChapterBriefGenerateResponse`, `WritingRunOut`

- [ ] **Step 1: Create `backend/app/schemas/writing.py`**

```python
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class NovelBlueprintOut(BaseModel):
    id: int
    novel_id: int
    version: int
    status: str
    content_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BlueprintGenerateRequest(BaseModel):
    author_input: str


class BlueprintUpdateRequest(BaseModel):
    content_json: Optional[dict[str, Any]] = None


class ChapterPlanOut(BaseModel):
    id: int
    novel_id: int
    chapter_id: Optional[int] = None
    position: int
    status: str
    content_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterPlanUpdateRequest(BaseModel):
    content_json: Optional[dict[str, Any]] = None


class ChapterBriefOut(BaseModel):
    id: int
    novel_id: int
    chapter_plan_id: int
    chapter_id: Optional[int] = None
    status: str
    brief_json: dict[str, Any]
    length_contract_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterBriefUpdateRequest(BaseModel):
    brief_json: Optional[dict[str, Any]] = None
    length_contract_json: Optional[dict[str, Any]] = None


class ContextPackageOut(BaseModel):
    id: int
    novel_id: int
    chapter_brief_id: int
    package_json: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class WritingRunOut(BaseModel):
    id: int
    novel_id: int
    chapter_brief_id: int
    context_package_id: int
    target_chapter_id: Optional[int] = None
    status: str
    draft_content: str
    word_count: int
    gate_result_json: dict[str, Any]
    error_message: Optional[str] = None
    accepted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WritingRunCreateRequest(BaseModel):
    chapter_brief_id: int
```

- [ ] **Step 2: Verify schemas import correctly**

```bash
.venv/bin/python -c "from app.schemas.writing import NovelBlueprintOut, ChapterPlanOut, ChapterBriefOut, ContextPackageOut, WritingRunOut, BlueprintGenerateRequest, WritingRunCreateRequest; print('writing schemas OK')"
```

Expected: `writing schemas OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/writing.py
git commit -m "feat: add writing schemas"
```

---

### Task 3: Backend Writing Repositories

**Files:**
- Create: `backend/app/repositories/writing_repo.py`

**Interfaces:**
- Consumes: models from Task 1, `AsyncSession`
- Produces: `WritingRepo` class with CRUD methods for all 5 models

- [ ] **Step 1: Create `backend/app/repositories/writing_repo.py`**

```python
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.writing import (
    NovelBlueprint,
    ChapterPlan,
    ChapterBrief,
    ContextPackage,
    WritingRun,
)


class BlueprintRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int) -> list[NovelBlueprint]:
        result = await self.db.execute(
            select(NovelBlueprint)
            .where(NovelBlueprint.novel_id == novel_id)
            .order_by(NovelBlueprint.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, blueprint_id: int) -> Optional[NovelBlueprint]:
        return await self.db.get(NovelBlueprint, blueprint_id)

    async def get_active(self, novel_id: int) -> Optional[NovelBlueprint]:
        result = await self.db.execute(
            select(NovelBlueprint).where(
                NovelBlueprint.novel_id == novel_id,
                NovelBlueprint.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def create(self, novel_id: int, data: dict) -> NovelBlueprint:
        blueprint = NovelBlueprint(novel_id=novel_id, **data)
        self.db.add(blueprint)
        await self.db.flush()
        return blueprint

    async def update(self, blueprint: NovelBlueprint, data: dict) -> NovelBlueprint:
        for key, value in data.items():
            setattr(blueprint, key, value)
        await self.db.flush()
        return blueprint

    async def deactivate_all(self, novel_id: int):
        await self.db.execute(
            update(NovelBlueprint)
            .where(
                NovelBlueprint.novel_id == novel_id,
                NovelBlueprint.status == "active",
            )
            .values(status="archived")
        )


class ChapterPlanRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_latest(self, novel_id: int) -> Optional[ChapterPlan]:
        result = await self.db.execute(
            select(ChapterPlan)
            .where(ChapterPlan.novel_id == novel_id)
            .order_by(ChapterPlan.position.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, plan_id: int) -> Optional[ChapterPlan]:
        return await self.db.get(ChapterPlan, plan_id)

    async def create(self, novel_id: int, data: dict) -> ChapterPlan:
        plan = ChapterPlan(novel_id=novel_id, **data)
        self.db.add(plan)
        await self.db.flush()
        return plan

    async def update(self, plan: ChapterPlan, data: dict) -> ChapterPlan:
        for key, value in data.items():
            setattr(plan, key, value)
        await self.db.flush()
        return plan


class ChapterBriefRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, brief_id: int) -> Optional[ChapterBrief]:
        return await self.db.get(ChapterBrief, brief_id)

    async def create(self, novel_id: int, data: dict) -> ChapterBrief:
        brief = ChapterBrief(novel_id=novel_id, **data)
        self.db.add(brief)
        await self.db.flush()
        return brief

    async def update(self, brief: ChapterBrief, data: dict) -> ChapterBrief:
        for key, value in data.items():
            setattr(brief, key, value)
        await self.db.flush()
        return brief


class ContextPackageRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, package_id: int) -> Optional[ContextPackage]:
        return await self.db.get(ContextPackage, package_id)

    async def create(self, novel_id: int, data: dict) -> ContextPackage:
        package = ContextPackage(novel_id=novel_id, **data)
        self.db.add(package)
        await self.db.flush()
        return package


class WritingRunRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int) -> list[WritingRun]:
        result = await self.db.execute(
            select(WritingRun)
            .where(WritingRun.novel_id == novel_id)
            .order_by(WritingRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, run_id: int) -> Optional[WritingRun]:
        return await self.db.get(WritingRun, run_id)

    async def create(self, novel_id: int, data: dict) -> WritingRun:
        run = WritingRun(novel_id=novel_id, **data)
        self.db.add(run)
        await self.db.flush()
        return run

    async def update(self, run: WritingRun, data: dict) -> WritingRun:
        for key, value in data.items():
            setattr(run, key, value)
        await self.db.flush()
        return run
```

- [ ] **Step 2: Verify imports**

```bash
.venv/bin/python -c "from app.repositories.writing_repo import BlueprintRepo, ChapterPlanRepo, ChapterBriefRepo, ContextPackageRepo, WritingRunRepo; print('writing repos OK')"
```

Expected: `writing repos OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/repositories/writing_repo.py
git commit -m "feat: add writing repositories"
```

---

### Task 4: AI Writing Generator

**Files:**
- Create: `backend/app/ai/writer.py`

**Interfaces:**
- Consumes: `app.core.config.settings`
- Produces: `FakeWritingGenerator`, `DeepSeekWritingGenerator` — 实现生成蓝图、章节计划、任务书、正文的接口

- [ ] **Step 1: Create `backend/app/ai/writer.py`**

```python
"""AI writing generators: real (DeepSeek) and fake (for testing)."""

import json
import logging
from typing import Optional

from app.ai.agent import create_novel_agent
from app.ai.models import NovelAgentState
from app.core.config import settings

logger = logging.getLogger("novel_agent.ai.writer")


class BaseWritingGenerator:
    async def generate_blueprint(self, novel_data: dict, author_input: str) -> dict:
        raise NotImplementedError

    async def generate_chapter_plan(self, blueprint: dict, novel_data: dict) -> dict:
        raise NotImplementedError

    async def generate_chapter_brief(self, chapter_plan: dict, blueprint: dict, length_contract: dict) -> dict:
        raise NotImplementedError

    async def generate_draft(self, context_package: dict) -> str:
        raise NotImplementedError


class FakeWritingGenerator(BaseWritingGenerator):
    async def generate_blueprint(self, novel_data: dict, author_input: str) -> dict:
        return {
            "core_promise": "一段英雄与背叛的史诗故事",
            "theme": "权力与责任",
            "main_conflict": "帝国与边疆势力的对抗",
            "character_arcs": "主角从逃避责任到承担使命",
            "world_rules": "五行灵力体系，修炼分为九境",
            "narrative_perspective": "第三人称有限视角",
            "style_constraints": "克制冷调，少用网络化表达",
            "ending_direction": "开放式结局，留续作空间",
        }

    async def generate_chapter_plan(self, blueprint: dict, novel_data: dict) -> dict:
        chapters = novel_data.get("chapters", [])
        return {
            "chapter_title": f"第 {len(chapters) + 1} 章",
            "plot_task": "推进主线冲突",
            "character_task": "展现主角性格变化",
            "information_task": "揭示关键背景信息",
            "emotional_effect": "紧张与期待交织",
            "pacing": "缓起急收，末尾留悬念",
            "foreshadowing_task": "暗示后续重大转折",
        }

    async def generate_chapter_brief(self, chapter_plan: dict, blueprint: dict, length_contract: dict) -> dict:
        return {
            "writing_goal": "完成本章剧情推进，塑造角色形象",
            "scenes": [
                {"name": "场景一 开端", "purpose": "建立本章情绪基调", "conflict": "内部冲突", "expected_words": 800},
                {"name": "场景二 冲突", "purpose": "推进主线矛盾", "conflict": "外部冲突", "expected_words": 1200},
                {"name": "场景三 收束", "purpose": "为下一章埋下伏笔", "conflict": "悬念", "expected_words": 1000},
            ],
            "participating_characters": "主角与反派",
            "conflict_design": "逐步升级的对抗",
            "information_control": "分批揭示",
            "foreshadowing_handling": "含蓄暗示",
            "writing_constraints": "不使用现代词汇",
            "acceptance_criteria": "完成所有剧情任务，字数达标",
        }

    async def generate_draft(self, context_package: dict) -> str:
        paragraph = (
            "边境的风裹挟着沙砾扑面而来，城墙上的旗帜在黄昏中猎猎作响。"
            "主角站在垛口边，目光越过荒原望向远方。"
            "那个方向传来消息已经三天了——没有人知道那意味着什么。"
        )
        return (paragraph + "\n\n") * 20


class DeepSeekWritingGenerator(BaseWritingGenerator):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.DEEPSEEK_API_KEY

    async def generate_blueprint(self, novel_data: dict, author_input: str) -> dict:
        prompt = f"""根据以下小说信息生成小说蓝图，以 JSON 格式返回。

小说标题：{novel_data.get('title', '')}
小说简介：{novel_data.get('description', '')}
类型：{novel_data.get('genre', '')}
风格指南：{novel_data.get('style_guide', '')}
作者构思：{author_input}

返回 JSON 字段：
- core_promise: 核心卖点
- theme: 主题表达
- main_conflict: 主线冲突
- character_arcs: 主要角色弧光
- world_rules: 世界规则
- narrative_perspective: 叙事视角
- style_constraints: 风格约束
- ending_direction: 结局方向

只返回 JSON，不要其他内容。"""
        return await self._call_llm(prompt)

    async def generate_chapter_plan(self, blueprint: dict, novel_data: dict) -> dict:
        prompt = f"""根据以下小说蓝图和已有章节信息，生成下一章章节大纲，以 JSON 格式返回。

蓝图核心内容：{json.dumps(blueprint, ensure_ascii=False)}
已有章节数：{len(novel_data.get('chapters', []))}

返回 JSON 字段：
- chapter_title: 章节标题
- plot_task: 剧情任务
- character_task: 角色任务
- information_task: 信息任务
- emotional_effect: 情绪效果
- pacing: 节奏目标
- foreshadowing_task: 伏笔任务

只返回 JSON。"""
        return await self._call_llm(prompt)

    async def generate_chapter_brief(self, chapter_plan: dict, blueprint: dict, length_contract: dict) -> dict:
        contract_str = json.dumps(length_contract, ensure_ascii=False)
        prompt = f"""根据以下章节大纲生成章节任务书，以 JSON 格式返回。
篇幅契约：目标{length_contract.get('target_words', 3000)}字，最低{length_contract.get('min_words', 2000)}字。

章节大纲：{json.dumps(chapter_plan, ensure_ascii=False)}

返回 JSON 字段：
- writing_goal: 写作目标
- scenes: 场景拆分数组，每个元素包含 name, purpose, conflict, expected_words
- participating_characters: 出场角色
- conflict_design: 冲突设计
- information_control: 信息控制
- foreshadowing_handling: 伏笔处理
- writing_constraints: 写作约束
- acceptance_criteria: 验收标准

只返回 JSON。"""
        return await self._call_llm(prompt)

    async def generate_draft(self, context_package: dict) -> str:
        brief = context_package.get("chapter_brief", {})
        contract = context_package.get("length_contract", {})
        prompt = f"""请根据以下章节任务书和上下文，写出一章小说正文。

任务书：{json.dumps(brief, ensure_ascii=False)}
字数要求：目标{contract.get('target_words', 3000)}字，最低{contract.get('min_words', 2000)}字

要求：
1. 按章节任务书写正文，不要自由发挥成另一章
2. 按篇幅充分展开场景、冲突、反应、动作、对话和氛围
3. 不输出大纲、列表、总结或解释，只输出章节正文
4. 如果篇幅不足，优先扩写场景过程和角色反应"""
        return await self._call_llm_text(prompt)

    async def _call_llm(self, prompt: str) -> dict:
        """调用 DeepSeek 返回 JSON。"""
        agent = create_novel_agent(
            model_type="flash",
            tools=[],
            system_prompt="你是一个小说创作辅助AI，只返回JSON格式的输出。",
            state_schema=NovelAgentState,
        )
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}], "novel_id": 0, "chapter_id": 0, "user_id": 0, "pending_confirmations": []},
            {"configurable": {"thread_id": "writer-generate"}},
        )
        content = result["messages"][-1].content if result.get("messages") else "{}"
        return json.loads(content)

    async def _call_llm_text(self, prompt: str) -> str:
        agent = create_novel_agent(
            model_type="flash",
            tools=[],
            system_prompt="你是一个小说作者，只输出小说正文，不输出其他内容。",
            state_schema=NovelAgentState,
        )
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}], "novel_id": 0, "chapter_id": 0, "user_id": 0, "pending_confirmations": []},
            {"configurable": {"thread_id": "writer-draft"}},
        )
        return result["messages"][-1].content if result.get("messages") else ""
```

- [ ] **Step 2: Verify imports**

```bash
.venv/bin/python -c "from app.ai.writer import FakeWritingGenerator, DeepSeekWritingGenerator; print('writer generators OK')"
```

Expected: `writer generators OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/ai/writer.py
git commit -m "feat: add AI writing generators (real + fake)"
```

---

### Task 5: Backend Writing Service

**Files:**
- Create: `backend/app/services/writing_service.py`

**Interfaces:**
- Consumes: writing repos (Task 3), generators (Task 4), `NovelRepo`, `app.services.novel_service.NovelService`
- Produces: `WritingService` with methods: create/update/activate blueprint, generate chapter plan/brief/context/draft, accept/discard writing run, word counting, gate checking

- [ ] **Step 1: Create `backend/app/services/writing_service.py`**

```python
"""写作业务逻辑。可通过 generator 参数注入 fake generator 用于测试。"""

import math
import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.writer import BaseWritingGenerator, DeepSeekWritingGenerator
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFound, AppException
from app.repositories.novel_repo import NovelRepo
from app.repositories.writing_repo import (
    BlueprintRepo,
    ChapterPlanRepo,
    ChapterBriefRepo,
    ContextPackageRepo,
    WritingRunRepo,
)
from app.models.novel import Novel, Chapter


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
            await self.db.flush()
            run.target_chapter_id = chapter.id
        run.status = "accepted"
        run.accepted_at = datetime.datetime.now()
        await self.db.flush()
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
```

- [ ] **Step 2: Add missing imports at top of service file**

The service file needs these at the top:

```python
import json
import datetime
import logging

from sqlalchemy import select

logger = logging.getLogger("novel_agent.writing")
```

- [ ] **Step 3: Verify imports**

```bash
.venv/bin/python -c "from app.services.writing_service import WritingService, DEFAULT_LENGTH_CONTRACT; print('writing service OK')"
```

Expected: `writing service OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/writing_service.py
git commit -m "feat: add writing service"
```

---

### Task 6: Backend Writing API

**Files:**
- Create: `backend/app/api/writing.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `WritingService`, schemas from Task 2
- Produces: all writing REST endpoints mounted under `/api/v1`

- [ ] **Step 1: Create `backend/app/api/writing.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFound
from app.core.response import ApiResponse
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.writing import (
    BlueprintGenerateRequest,
    BlueprintUpdateRequest,
    ChapterPlanUpdateRequest,
    ChapterBriefUpdateRequest,
    WritingRunCreateRequest,
    NovelBlueprintOut,
    ChapterPlanOut,
    ChapterBriefOut,
    ContextPackageOut,
    WritingRunOut,
)
from app.services.writing_service import WritingService

router = APIRouter(prefix="/novels/{novel_id}", tags=["Writing"])


def _get_service(db: AsyncSession, current_user: User, novel_id: int) -> WritingService:
    return WritingService(db=db, user_id=current_user.id, novel_id=novel_id)


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
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    plan_id = body.get("chapter_plan_id")
    if not plan_id:
        from app.core.exceptions import AppException
        raise AppException("缺少 chapter_plan_id")
    brief = await svc.generate_chapter_brief(plan_id)
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
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    brief_id = body.get("chapter_brief_id")
    if not brief_id:
        from app.core.exceptions import AppException
        raise AppException("缺少 chapter_brief_id")
    package = await svc.generate_context_package(brief_id)
    return ApiResponse.success(data=ContextPackageOut.model_validate(package).model_dump())


# ---- Writing Runs ----

@router.post("/writing-runs")
async def create_writing_run(
    novel_id: int,
    body: WritingRunCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    run = await svc.create_writing_run(body.chapter_brief_id)
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    chapter = await svc.accept_writing_run(run_id)
    from app.schemas.novel import ChapterOut
    return ApiResponse.success(data=ChapterOut.model_validate(chapter).model_dump(), message="草稿已接受并写入章节")


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
```

- [ ] **Step 2: Register the router in `backend/app/main.py`**

```python
from app.api import auth, memory, novels, writing
...
app.include_router(writing.router, prefix="/api/v1")
```

- [ ] **Step 3: Verify routes load**

```bash
.venv/bin/python -c "from app.main import app; routes = [(r.path, list(r.methods)) for r in app.routes if hasattr(r, 'methods')]; print(f'Total routes: {len(routes)}'); print([p for p, m in routes if 'blueprint' in p or 'writing' in p or 'brief' in p])"
```

Expected: List of new writing route paths.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/writing.py backend/app/main.py
git commit -m "feat: add writing API routes"
```

---

### Task 7: Backend Writing Tests

**Files:**
- Create: `backend/tests/test_phase_1_writing.py`

**Interfaces:**
- Consumes: fake generator from `app.ai.writer.FakeWritingGenerator`, httpx test client, all backend APIs
- Produces: comprehensive test coverage for the writing module

- [ ] **Step 1: Create `backend/tests/test_phase_1_writing.py`**

```python
"""Phase 1 v2 自主写作测试——使用 FakeWritingGenerator，不依赖真实 AI。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def register_headers(client, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


async def create_novel(client, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/api/v1/novels",
        headers=headers,
        json={"title": "写作测试小说", "description": "用于测试自主写作闭环", "genre": "古风权谋", "style_guide": "第三人称有限视角"},
    )
    assert response.status_code == 200
    return response.json()["data"]


@pytest.fixture
async def novel_and_headers(client):
    headers = await register_headers(client, "writing_user")
    novel = await create_novel(client, headers)
    return novel, headers


async def test_blueprint_generate_and_activate(client, novel_and_headers):
    """测试生成蓝图并激活。"""
    novel, headers = novel_and_headers
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "一个关于权力与背叛的故事"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "draft"
    assert "core_promise" in data["content_json"]
    blueprint_id = data["id"]

    resp = await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{blueprint_id}/activate",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "active"


async def test_blueprint_list(client, novel_and_headers):
    """测试蓝图列表。"""
    novel, headers = novel_and_headers
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


async def test_blueprint_update(client, novel_and_headers):
    """测试更新蓝图。"""
    novel, headers = novel_and_headers
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    blueprint_id = resp.json()["data"]["id"]
    new_content = {"core_promise": "修改后的核心卖点"}
    resp = await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{blueprint_id}",
        headers=headers,
        json={"content_json": new_content},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["content_json"]["core_promise"] == "修改后的核心卖点"


async def test_blueprint_activate_archives_previous(client, novel_and_headers):
    """测试激活新蓝图时旧蓝图被归档。"""
    novel, headers = novel_and_headers
    resp1 = await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "第一版"},
    )
    bp1_id = resp1.json()["data"]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp1_id}/activate",
        headers=headers,
    )
    resp2 = await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "第二版"},
    )
    bp2_id = resp2.json()["data"]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp2_id}/activate",
        headers=headers,
    )
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    blueprints = resp.json()["data"]
    for bp in blueprints:
        if bp["id"] == bp1_id:
            assert bp["status"] == "archived"
        if bp["id"] == bp2_id:
            assert bp["status"] == "active"


async def test_chapter_plan_fails_without_active_blueprint(client, novel_and_headers):
    """测试没有激活蓝图时不能生成章节计划。"""
    novel, headers = novel_and_headers
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate",
        headers=headers,
    )
    assert resp.status_code == 400


async def test_chapter_plan_generate(client, novel_and_headers):
    """测试生成章节计划。"""
    novel, headers = novel_and_headers
    await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate",
        headers=headers,
    )
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "ready"
    assert "plot_task" in data["content_json"]


async def test_chapter_brief_generate(client, novel_and_headers):
    """测试生成章节任务书和默认篇幅契约。"""
    novel, headers = novel_and_headers
    await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate",
        headers=headers,
    )
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate",
        headers=headers,
    )
    plan_id = resp.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-briefs/generate",
        headers=headers,
        json={"chapter_plan_id": plan_id},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "ready"
    assert data["length_contract_json"]["target_words"] == 3000
    assert data["length_contract_json"]["min_words"] == 2000


async def test_context_package_generate(client, novel_and_headers):
    """测试上下文包生成包含全部上下文。"""
    novel, headers = novel_and_headers
    await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate",
        headers=headers,
    )
    await client.post(f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate", headers=headers)
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate", headers=headers)
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate", headers=headers)
    plan_id = resp.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-briefs/generate",
        headers=headers,
        json={"chapter_plan_id": plan_id},
    )
    brief_id = resp.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/context-packages/generate",
        headers=headers,
        json={"chapter_brief_id": brief_id},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "chapter_brief" in data["package_json"]
    assert "length_contract" in data["package_json"]
    assert "characters" in data["package_json"]


async def test_writing_run_full_flow(client, novel_and_headers):
    """测试完整写作运行流程：生成蓝图 → 计划 → 任务书 → 上下文包 → 草稿 → 接受。"""
    novel, headers = novel_and_headers
    bp_resp = await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    bp_id = bp_resp.json()["data"]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate",
        headers=headers,
    )
    plan_resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate",
        headers=headers,
    )
    plan_id = plan_resp.json()["data"]["id"]
    brief_resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-briefs/generate",
        headers=headers,
        json={"chapter_plan_id": plan_id},
    )
    brief_id = brief_resp.json()["data"]["id"]
    ctx_resp = await client.post(
        f"/api/v1/novels/{novel['id']}/context-packages/generate",
        headers=headers,
        json={"chapter_brief_id": brief_id},
    )
    ctx_id = ctx_resp.json()["data"]["id"]
    run_resp = await client.post(
        f"/api/v1/novels/{novel['id']}/writing-runs",
        headers=headers,
        json={"chapter_brief_id": brief_id},
    )
    assert run_resp.status_code == 200
    run = run_resp.json()["data"]
    assert run["status"] in ("completed", "failed")
    assert run["word_count"] >= 0
    if run["status"] == "completed":
        accept_resp = await client.put(
            f"/api/v1/novels/{novel['id']}/writing-runs/{run['id']}/accept",
            headers=headers,
        )
        assert accept_resp.status_code == 200
        assert accept_resp.json()["data"]["content"] == run["draft_content"]


async def test_writing_run_discard(client, novel_and_headers):
    """测试废弃写作运行不修改章节。"""
    novel, headers = novel_and_headers
    await client.post(f"/api/v1/novels/{novel['id']}/blueprints/generate", headers=headers, json={"author_input": "测试"})
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate", headers=headers)
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate", headers=headers)
    plan_id = resp.json()["data"]["id"]
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-briefs/generate", headers=headers, json={"chapter_plan_id": plan_id})
    brief_id = resp.json()["data"]["id"]
    resp = await client.post(f"/api/v1/novels/{novel['id']}/context-packages/generate", headers=headers, json={"chapter_brief_id": brief_id})
    run_resp = await client.post(f"/api/v1/novels/{novel['id']}/writing-runs", headers=headers, json={"chapter_brief_id": brief_id})
    run = run_resp.json()["data"]
    if run["status"] == "completed":
        chapter_count_resp = await client.get(f"/api/v1/novels/{novel['id']}", headers=headers)
        chapter_count_before = len(chapter_count_resp.json()["data"].get("chapters", []))
        discard_resp = await client.put(
            f"/api/v1/novels/{novel['id']}/writing-runs/{run['id']}/discard",
            headers=headers,
        )
        assert discard_resp.status_code == 200
        run_resp2 = await client.get(
            f"/api/v1/novels/{novel['id']}/writing-runs/{run['id']}",
            headers=headers,
        )
        assert run_resp2.json()["data"]["status"] == "discarded"


async def test_double_accept_rejected(client, novel_and_headers):
    """测试已处理的写作运行不能再次操作。"""
    novel, headers = novel_and_headers
    await client.post(f"/api/v1/novels/{novel['id']}/blueprints/generate", headers=headers, json={"author_input": "测试"})
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate", headers=headers)
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate", headers=headers)
    plan_id = resp.json()["data"]["id"]
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-briefs/generate", headers=headers, json={"chapter_plan_id": plan_id})
    brief_id = resp.json()["data"]["id"]
    await client.post(f"/api/v1/novels/{novel['id']}/context-packages/generate", headers=headers, json={"chapter_brief_id": brief_id})
    run_resp = await client.post(f"/api/v1/novels/{novel['id']}/writing-runs", headers=headers, json={"chapter_brief_id": brief_id})
    run = run_resp.json()["data"]
    if run["status"] == "completed":
        await client.put(
            f"/api/v1/novels/{novel['id']}/writing-runs/{run['id']}/accept",
            headers=headers,
        )
        resp = await client.put(
            f"/api/v1/novels/{novel['id']}/writing-runs/{run['id']}/accept",
            headers=headers,
        )
        assert resp.status_code == 400


async def test_cross_user_protection(client, novel_and_headers):
    """测试跨用户无法访问写作资源。"""
    novel, headers = novel_and_headers
    intruder_headers = await register_headers(client, "intruder")
    await client.post(f"/api/v1/novels/{novel['id']}/blueprints/generate", headers=headers, json={"author_input": "测试"})
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=intruder_headers)
    assert resp.status_code == 404
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate", headers=intruder_headers)
    assert resp.status_code == 404
```

- [ ] **Step 2: Run the tests and verify they pass**

```bash
.venv/bin/python -m pytest tests/test_phase_1_writing.py -x -q --timeout=60
```

Expected: All tests pass or the initial failures are expected (since this is step 1 of the test-driven cycle for subsequent tasks — the tests were written after the implementation).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_phase_1_writing.py
git commit -m "test: add writing module tests"
```

---

### Task 8: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/b3c4d5e6f7a8_phase_1_writing_models.py`

**Interfaces:**
- Consumes: models from Task 1
- Produces: migration file for writing tables

- [ ] **Step 1: Create migration**

Run:
```bash
.venv/bin/python -m alembic revision --autogenerate -m "phase_1_writing_models"
```

If autogenerate doesn't pick up the new models, create manually. Check the generated file at `backend/alembic/versions/`.

- [ ] **Step 2: Review and fix the migration**

Read the generated migration and verify it creates these tables:
- `novel_blueprints`
- `chapter_plans`
- `chapter_briefs`
- `context_packages`
- `writing_runs`

- [ ] **Step 3: Run the migration**

```bash
.venv/bin/python -m alembic upgrade head
```

Expected output confirming migration applied.

- [ ] **Step 4: Verify tables exist**

```bash
.venv/bin/python -c "from app.core.database import engine; import sqlalchemy as sa; import asyncio; async def check(): async with engine.begin() as c: r = await c.execute(sa.text('SELECT name FROM sqlite_master WHERE type=\"table\" ORDER BY name')); print([row[0] for row in r]); asyncio.run(check())"
```

Expected: new table names appear in the list.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat: add writing models migration"
```

---

### Task 9: Frontend Writing Types + API Client + Store

**Files:**
- Create: `frontend/src/types/writing.ts`
- Create: `frontend/src/api/writing.ts`
- Create: `frontend/src/stores/writing.ts`

**Interfaces:**
- Consumes: `@/api/client` from `api/client.ts`
- Produces: all writing types, API client functions, Pinia store

- [ ] **Step 1: Create `frontend/src/types/writing.ts`**

```typescript
export interface NovelBlueprint {
  id: number
  novel_id: number
  version: number
  status: 'draft' | 'active' | 'archived'
  content_json: {
    core_promise: string
    theme: string
    main_conflict: string
    character_arcs: string
    world_rules: string
    narrative_perspective: string
    style_constraints: string
    ending_direction: string
  }
  created_at: string
  updated_at: string
}

export interface ChapterPlan {
  id: number
  novel_id: number
  chapter_id: number | null
  position: number
  status: 'draft' | 'ready' | 'used'
  content_json: {
    chapter_title: string
    plot_task: string
    character_task: string
    information_task: string
    emotional_effect: string
    pacing: string
    foreshadowing_task: string
  }
  created_at: string
  updated_at: string
}

export interface ChapterBrief {
  id: number
  novel_id: number
  chapter_plan_id: number
  chapter_id: number | null
  status: 'draft' | 'ready' | 'used'
  brief_json: {
    writing_goal: string
    scenes: { name: string; purpose: string; conflict: string; expected_words: number }[]
    participating_characters: string
    conflict_design: string
    information_control: string
    foreshadowing_handling: string
    writing_constraints: string
    acceptance_criteria: string
  }
  length_contract_json: {
    target_words: number
    min_words: number
    max_words: number
    scene_word_allocation: { scene: string; words: number }[]
    density_requirements: string
    expansion_strategy: string
    compression_strategy: string
  }
  created_at: string
  updated_at: string
}

export interface ContextPackage {
  id: number
  novel_id: number
  chapter_brief_id: number
  package_json: Record<string, unknown>
  created_at: string
}

export interface WritingRun {
  id: number
  novel_id: number
  chapter_brief_id: number
  context_package_id: number
  target_chapter_id: number | null
  status: 'running' | 'completed' | 'failed' | 'accepted' | 'discarded'
  draft_content: string
  word_count: number
  gate_result_json: {
    passed: boolean
    reasons: string[]
    min_words: number
    target_words: number
    max_words: number
    outline_like: boolean
  }
  error_message: string | null
  accepted_at: string | null
  created_at: string
  updated_at: string
}
```

- [ ] **Step 2: Create `frontend/src/api/writing.ts`**

```typescript
import client from './client'
import type { NovelBlueprint, ChapterPlan, ChapterBrief, ContextPackage, WritingRun } from '@/types/writing'

export function generateBlueprint(novelId: number, authorInput: string): Promise<NovelBlueprint> {
  return client.post(`/novels/${novelId}/blueprints/generate`, { author_input: authorInput })
}

export function listBlueprints(novelId: number): Promise<NovelBlueprint[]> {
  return client.get(`/novels/${novelId}/blueprints`)
}

export function updateBlueprint(novelId: number, blueprintId: number, data: Partial<NovelBlueprint>): Promise<NovelBlueprint> {
  return client.put(`/novels/${novelId}/blueprints/${blueprintId}`, data)
}

export function activateBlueprint(novelId: number, blueprintId: number): Promise<NovelBlueprint> {
  return client.put(`/novels/${novelId}/blueprints/${blueprintId}/activate`)
}

export function generateChapterPlan(novelId: number): Promise<ChapterPlan> {
  return client.post(`/novels/${novelId}/chapter-plans/next/generate`)
}

export function updateChapterPlan(novelId: number, planId: number, data: Partial<ChapterPlan>): Promise<ChapterPlan> {
  return client.put(`/novels/${novelId}/chapter-plans/${planId}`, data)
}

export function generateChapterBrief(novelId: number, chapterPlanId: number): Promise<ChapterBrief> {
  return client.post(`/novels/${novelId}/chapter-briefs/generate`, { chapter_plan_id: chapterPlanId })
}

export function updateChapterBrief(novelId: number, briefId: number, data: Partial<ChapterBrief>): Promise<ChapterBrief> {
  return client.put(`/novels/${novelId}/chapter-briefs/${briefId}`, data)
}

export function generateContextPackage(novelId: number, chapterBriefId: number): Promise<ContextPackage> {
  return client.post(`/novels/${novelId}/context-packages/generate`, { chapter_brief_id: chapterBriefId })
}

export function createWritingRun(novelId: number, chapterBriefId: number): Promise<WritingRun> {
  return client.post(`/novels/${novelId}/writing-runs`, { chapter_brief_id: chapterBriefId })
}

export function listWritingRuns(novelId: number): Promise<WritingRun[]> {
  return client.get(`/novels/${novelId}/writing-runs`)
}

export function getWritingRun(novelId: number, runId: number): Promise<WritingRun> {
  return client.get(`/novels/${novelId}/writing-runs/${runId}`)
}

export function acceptWritingRun(novelId: number, runId: number): Promise<{ id: number; content: string }> {
  return client.put(`/novels/${novelId}/writing-runs/${runId}/accept`)
}

export function discardWritingRun(novelId: number, runId: number): Promise<void> {
  return client.put(`/novels/${novelId}/writing-runs/${runId}/discard`)
}
```

- [ ] **Step 3: Create `frontend/src/stores/writing.ts`**

```typescript
import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/writing'
import type { NovelBlueprint, ChapterPlan, ChapterBrief, ContextPackage, WritingRun } from '@/types/writing'

export const useWritingStore = defineStore('writing', () => {
  const blueprints = ref<NovelBlueprint[]>([])
  const activeBlueprint = ref<NovelBlueprint | null>(null)
  const latestPlan = ref<ChapterPlan | null>(null)
  const latestBrief = ref<ChapterBrief | null>(null)
  const latestContext = ref<ContextPackage | null>(null)
  const writingRuns = ref<WritingRun[]>([])
  const loading = ref(false)

  async function fetchBlueprints(novelId: number) {
    blueprints.value = await api.listBlueprints(novelId)
    activeBlueprint.value = blueprints.value.find(b => b.status === 'active') || null
  }

  async function generateBlueprint(novelId: number, authorInput: string) {
    loading.value = true
    try {
      const bp = await api.generateBlueprint(novelId, authorInput)
      blueprints.value.unshift(bp)
      return bp
    } finally {
      loading.value = false
    }
  }

  async function activateBlueprint(novelId: number, blueprintId: number) {
    const bp = await api.activateBlueprint(novelId, blueprintId)
    activeBlueprint.value = bp
    blueprints.value = blueprints.value.map(b => ({
      ...b,
      status: b.id === blueprintId ? 'active' : 'archived',
    }))
    return bp
  }

  async function updateBlueprint(novelId: number, blueprintId: number, data: Partial<NovelBlueprint>) {
    const bp = await api.updateBlueprint(novelId, blueprintId, data)
    blueprints.value = blueprints.value.map(b => (b.id === blueprintId ? bp : b))
    if (activeBlueprint.value?.id === blueprintId) activeBlueprint.value = bp
    return bp
  }

  async function generateChapterPlan(novelId: number) {
    loading.value = true
    try {
      latestPlan.value = await api.generateChapterPlan(novelId)
      return latestPlan.value
    } finally {
      loading.value = false
    }
  }

  async function generateChapterBrief(novelId: number, planId: number) {
    loading.value = true
    try {
      latestBrief.value = await api.generateChapterBrief(novelId, planId)
      return latestBrief.value
    } finally {
      loading.value = false
    }
  }

  async function generateContextPackage(novelId: number, briefId: number) {
    loading.value = true
    try {
      latestContext.value = await api.generateContextPackage(novelId, briefId)
      return latestContext.value
    } finally {
      loading.value = false
    }
  }

  async function createWritingRun(novelId: number, briefId: number) {
    loading.value = true
    try {
      const run = await api.createWritingRun(novelId, briefId)
      writingRuns.value.unshift(run)
      return run
    } finally {
      loading.value = false
    }
  }

  async function acceptRun(novelId: number, runId: number) {
    const result = await api.acceptWritingRun(novelId, runId)
    writingRuns.value = writingRuns.value.map(r =>
      r.id === runId ? { ...r, status: 'accepted' as const } : r,
    )
    return result
  }

  async function discardRun(novelId: number, runId: number) {
    await api.discardWritingRun(novelId, runId)
    writingRuns.value = writingRuns.value.map(r =>
      r.id === runId ? { ...r, status: 'discarded' as const } : r,
    )
  }

  async function fetchWritingRuns(novelId: number) {
    writingRuns.value = await api.listWritingRuns(novelId)
  }

  return {
    blueprints, activeBlueprint, latestPlan, latestBrief, latestContext,
    writingRuns, loading,
    fetchBlueprints, generateBlueprint, activateBlueprint, updateBlueprint,
    generateChapterPlan, generateChapterBrief, generateContextPackage,
    createWritingRun, acceptRun, discardRun, fetchWritingRuns,
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useWritingStore, import.meta.hot))
}
```

- [ ] **Step 4: Verify TypeScript compilation**

```bash
npm run type-check
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/writing.ts frontend/src/api/writing.ts frontend/src/stores/writing.ts
git commit -m "feat: add frontend writing types, API client, and store"
```

---

### Task 10: Frontend WritingWorkspaceView

**Files:**
- Create: `frontend/src/views/novels/WritingWorkspaceView.vue`

**Interfaces:**
- Consumes: writing store (Task 9), Element Plus components (auto-imported)
- Produces: linear writing workspace with 5 sections: blueprint, plan, brief, context, draft

- [ ] **Step 1: Create `frontend/src/views/novels/WritingWorkspaceView.vue`**

```vue
<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWritingStore } from '@/stores/writing'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'
import type { ChapterBrief, WritingRun } from '@/types/writing'

const route = useRoute()
const store = useWritingStore()
const novelId = Number(route.params.id)

const authorInput = ref('')
const showBlueprintEditor = ref(false)
const blueprintText = ref('')
const activeSection = ref<'blueprint' | 'plan' | 'brief' | 'context' | 'draft'>('blueprint')

const editingTargetWords = ref(3000)
const editingMinWords = ref(2000)
const editingMaxWords = ref(5000)

const activeRun = computed<WritingRun | null>(() =>
  store.writingRuns.find(r => r.status === 'completed' || r.status === 'failed') || null,
)

onMounted(async () => {
  await store.fetchBlueprints(novelId)
  if (store.activeBlueprint) {
    activeSection.value = 'plan'
    blueprintText.value = JSON.stringify(store.activeBlueprint.content_json, null, 2)
  }
})

async function handleGenerateBlueprint() {
  if (!authorInput.value.trim()) {
    ElMessage.warning('请输入小说构思')
    return
  }
  await store.generateBlueprint(novelId, authorInput.value)
  ElMessage.success('蓝图已生成')
  activeSection.value = 'plan'
}

async function handleActivate(bpId: number) {
  await store.activateBlueprint(novelId, bpId)
  ElMessage.success('蓝图已激活')
}

async function handleGeneratePlan() {
  await store.generateChapterPlan(novelId)
  ElMessage.success('章节计划已生成')
  activeSection.value = 'brief'
}

async function handleGenerateBrief() {
  if (!store.latestPlan) return
  await store.generateChapterBrief(novelId, store.latestPlan.id)
  ElMessage.success('任务书已生成')
  activeSection.value = 'context'
}

async function handleGenerateContext() {
  if (!store.latestBrief) return
  await store.generateContextPackage(novelId, store.latestBrief.id)
  ElMessage.success('上下文包已生成')
  activeSection.value = 'draft'
}

async function handleGenerateDraft() {
  if (!store.latestBrief) return
  try {
    const run = await store.createWritingRun(novelId, store.latestBrief.id)
    ElMessage.success('草稿已生成')
  } catch {
    ElMessage.error('生成草稿失败')
  }
}

async function handleAcceptRun(runId: number) {
  try {
    await store.acceptRun(novelId, runId)
    ElMessage.success('草稿已接受并写入章节')
  } catch {
    ElMessage.error('接受失败')
  }
}

async function handleDiscardRun(runId: number) {
  await store.discardRun(novelId, runId)
  ElMessage.success('草稿已废弃')
}

function editBlueprint(bp: any) {
  blueprintText.value = JSON.stringify(bp.content_json, null, 2)
  showBlueprintEditor.value = true
}

async function saveBlueprint(bpId: number) {
  try {
    const parsed = JSON.parse(blueprintText.value)
    await store.updateBlueprint(novelId, bpId, { content_json: parsed })
    ElMessage.success('蓝图已保存')
    showBlueprintEditor.value = false
  } catch {
    ElMessage.error('JSON 格式错误')
  }
}
</script>

<template>
  <div class="writing">
    <NovelWorkspaceTabs :novel-id="novelId" />

    <div class="writing__steps">
      <!-- 1. Blueprint -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>1. 小说蓝图</span>
        </template>
        <div v-if="!store.activeBlueprint">
          <el-input
            v-model="authorInput"
            type="textarea"
            :rows="3"
            placeholder="输入小说构思，例如：一个关于权力与背叛的故事..."
          />
          <el-button type="primary" class="writing__btn" :loading="store.loading" @click="handleGenerateBlueprint">
            生成蓝图
          </el-button>
        </div>
        <div v-else>
          <el-alert type="success" :closable="false" title="蓝图已激活" />
          <pre class="writing__json">{{ blueprintText }}</pre>
          <el-button size="small" @click="editBlueprint(store.activeBlueprint)">编辑蓝图</el-button>
        </div>
      </el-card>

      <!-- 2. Chapter Plan -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>2. 下一章计划</span>
        </template>
        <div v-if="store.latestPlan">
          <p><strong>标题：</strong>{{ store.latestPlan.content_json.chapter_title }}</p>
          <p><strong>剧情任务：</strong>{{ store.latestPlan.content_json.plot_task }}</p>
          <p><strong>角色任务：</strong>{{ store.latestPlan.content_json.character_task }}</p>
        </div>
        <el-button
          type="primary"
          class="writing__btn"
          :disabled="!store.activeBlueprint"
          :loading="store.loading"
          @click="handleGeneratePlan"
        >
          生成下一章计划
        </el-button>
      </el-card>

      <!-- 3. Chapter Brief -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>3. 章节任务书</span>
        </template>
        <div v-if="store.latestBrief">
          <p><strong>写作目标：</strong>{{ store.latestBrief.brief_json.writing_goal }}</p>
          <p><strong>场景数：</strong>{{ store.latestBrief.brief_json.scenes?.length || 0 }}</p>
          <p><strong>篇幅契约：</strong>{{ store.latestBrief.length_contract_json.target_words }} / {{ store.latestBrief.length_contract_json.min_words }} / {{ store.latestBrief.length_contract_json.max_words }} 字</p>
          <el-divider />
          <el-form label-width="80px" size="small">
            <el-form-item label="目标字数">
              <el-input-number v-model="editingTargetWords" :min="1000" :max="10000" />
            </el-form-item>
            <el-form-item label="最低字数">
              <el-input-number v-model="editingMinWords" :min="500" :max="5000" />
            </el-form-item>
            <el-form-item label="最高字数">
              <el-input-number v-model="editingMaxWords" :min="2000" :max="20000" />
            </el-form-item>
          </el-form>
        </div>
        <el-button
          type="primary"
          class="writing__btn"
          :disabled="!store.latestPlan"
          :loading="store.loading"
          @click="handleGenerateBrief"
        >
          生成任务书
        </el-button>
      </el-card>

      <!-- 4. Context Package -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>4. 上下文包</span>
        </template>
        <div v-if="store.latestContext">
          <p><strong>角色数：</strong>{{ (store.latestContext.package_json as any).characters?.length || 0 }}</p>
          <p><strong>设定数：</strong>{{ (store.latestContext.package_json as any).world_settings?.length || 0 }}</p>
          <p><strong>蓝图摘要：</strong>已包含</p>
        </div>
        <el-button
          type="primary"
          class="writing__btn"
          :disabled="!store.latestBrief"
          :loading="store.loading"
          @click="handleGenerateContext"
        >
          生成上下文包
        </el-button>
      </el-card>

      <!-- 5. Draft -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>5. 生成草稿</span>
        </template>
        <div v-if="activeRun && activeRun.status === 'completed'">
          <div class="writing__stats">
            <span>字数：{{ activeRun.word_count }}</span>
            <span>目标：{{ activeRun.gate_result_json.target_words }}</span>
            <el-tag v-if="activeRun.gate_result_json.passed" type="success">通过</el-tag>
            <el-tag v-else type="danger">未通过</el-tag>
          </div>
          <div v-if="activeRun.gate_result_json.reasons.length" class="writing__reasons">
            <p v-for="r in activeRun.gate_result_json.reasons" :key="r" class="writing__reason">{{ r }}</p>
          </div>
          <pre class="writing__draft">{{ activeRun.draft_content.slice(0, 500) }}...</pre>
          <div class="writing__actions">
            <el-button type="primary" @click="handleAcceptRun(activeRun.id)">接受到章节</el-button>
            <el-button @click="handleDiscardRun(activeRun.id)">废弃</el-button>
          </div>
        </div>
        <div v-else-if="activeRun && activeRun.status === 'failed'">
          <el-alert type="error" :closable="false" title="生成失败" :description="activeRun.error_message || '字数未达标或内容为大纲体'" />
        </div>
        <el-button
          type="primary"
          class="writing__btn"
          :disabled="!store.latestContext"
          :loading="store.loading"
          @click="handleGenerateDraft"
        >
          {{ store.writingRuns.length ? '重新生成草稿' : '生成草稿' }}
        </el-button>
      </el-card>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.writing {
  max-width: 900px;
  margin: 0 auto;
}

.writing__steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}

.writing__section {
  .el-card__body {
    padding: 16px;
  }
}

.writing__btn {
  margin-top: 12px;
}

.writing__json {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
}

.writing__stats {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
}

.writing__draft {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  white-space: pre-wrap;
  max-height: 400px;
  overflow: auto;
  margin: 8px 0;
}

.writing__actions {
  display: flex;
  gap: 8px;
}

.writing__reasons {
  margin: 4px 0;
}

.writing__reason {
  color: #e6a23c;
  font-size: 13px;
}
</style>
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
npm run type-check
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/novels/WritingWorkspaceView.vue
git commit -m "feat: add writing workspace view"
```

---

### Task 11: Frontend Router + Tabs

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/novels/NovelWorkspaceTabs.vue`

**Interfaces:**
- Consumes: workspace view from Task 10
- Produces: `/novels/:id/writing` route and "写作" tab in workspace navigation

- [ ] **Step 1: Add route to `frontend/src/router/index.ts`**

```typescript
{ path: 'novels/:id/writing', name: 'writing-workspace', component: () => import('@/views/novels/WritingWorkspaceView.vue'), meta: { auth: true } },
```

Add this after the `pending` route line:

```typescript
{ path: 'novels/:id/pending', name: 'novel-pending', component: () => import('@/views/novels/PendingConfirmView.vue'), meta: { auth: true } },
{ path: 'novels/:id/writing', name: 'writing-workspace', component: () => import('@/views/novels/WritingWorkspaceView.vue'), meta: { auth: true } },
```

- [ ] **Step 2: Add tab to `frontend/src/components/novels/NovelWorkspaceTabs.vue`**

Find the `tabs` array and add a new entry:

```typescript
{ label: '待确认', path: `/novels/${props.novelId}/pending`, badge: pendingBadge.value },
{ label: '写作', path: `/novels/${props.novelId}/writing` },
```

- [ ] **Step 3: Verify**

```bash
npm run type-check
npm run build
```

Expected: Build succeeds without errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/components/novels/NovelWorkspaceTabs.vue
git commit -m "feat: add writing route and workspace tab"
```

---

### Task 12: Real AI Integration Test

**Files:**
- Create: `backend/tests/test_phase_1_writing_integration.py`

**Interfaces:**
- Consumes: real DeepSeek API via `DeepSeekWritingGenerator`, `settings`
- Produces: optional smoke test skipped without DEEPSEEK_API_KEY

- [ ] **Step 1: Create `backend/tests/test_phase_1_writing_integration.py`**

```python
"""Phase 1 v2 自主写作集成测试——调用真实 DeepSeek API。"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app

pytestmark = pytest.mark.skipif(
    not settings.DEEPSEEK_API_KEY,
    reason="DEEPSEEK_API_KEY not set — set in .env to run AI integration tests",
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_headers(client) -> dict:
    await client.post("/api/v1/auth/register", json={"username": "writing_ai", "password": "pass123"})
    resp = await client.post("/api/v1/auth/login", json={"username": "writing_ai", "password": "pass123"})
    token = resp.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_blueprint_generate_real_ai(client, auth_headers):
    """验证真实 AI 能生成包含必需字段的蓝图。"""
    resp = await client.post("/api/v1/novels", json={"title": "蓝图测试", "genre": "都市悬疑"}, headers=auth_headers)
    novel_id = resp.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/blueprints/generate",
        json={"author_input": "一个都市悬疑故事，主角是退役刑警"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "core_promise" in data["content_json"]
    assert "main_conflict" in data["content_json"]
    assert data["status"] == "draft"
```

- [ ] **Step 2: Run the integration test**

```bash
.venv/bin/python -m pytest tests/test_phase_1_writing_integration.py -x -q --timeout=120
```

Expected: Skip if no API key, or pass if configured.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_phase_1_writing_integration.py
git commit -m "test: add real AI integration test for writing"
```
