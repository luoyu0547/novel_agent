# Phase 2: AI 骨架 + 章节提取闭环 实现计划

> **For agentic workers:** Use subagent-driven-development or executing-plans to implement task-by-task.

**Goal:** 搭建 LangChain 1.x AI 骨架，实现章节提取闭环（角色变化、剧情事实、新设定、伏笔候选），包含 PendingMemory 待确认区及前端确认页。

**Architecture:** LangChain 1.3 + langchain-deepseek，双 Agent 路径（Flash 标准 / Pro 深度），提取结果写入 PendingMemory → 用户确认后写入正式表。

**Tech Stack:** Python 3.12, LangChain 1.3.11, langchain-deepseek 1.1.0, deepagents, Vue 3 + Pinia + Element Plus

## Global Constraints

- 模型名由代码决定: `FLASH_MODEL = "deepseek-v4-flash"`, `PRO_MODEL = "deepseek-v4-pro"`
- 只有 `DEEPSEEK_API_KEY` 在 `.env` 中配置
- 测试调用真实 DeepSeek API，不 mock
- 所有 API 返回 `{"code": 0, "message": "ok", "data": ...}` 格式
- 遵循现有后端分层: api → service → repository → model
- 遵循现有前端模式: types → api → store → view

## File Structure

```
CREATE:
  backend/app/ai/__init__.py
  backend/app/ai/config.py
  backend/app/ai/models.py
  backend/app/ai/tools/__init__.py
  backend/app/ai/tools/context.py
  backend/app/ai/tools/memory.py
  backend/app/ai/middleware/__init__.py
  backend/app/ai/middleware/logging.py
  backend/app/ai/agent.py
  backend/app/ai/service.py
  backend/app/ai/router.py
  backend/app/models/pending_memory.py
  backend/app/models/plot_fact.py
  backend/app/models/foreshadowing.py
  backend/app/schemas/pending_memory.py
  backend/app/repositories/pending_memory_repo.py
  backend/tests/test_phase_2_ai_extract.py
  frontend/src/types/pendingMemory.ts
  frontend/src/types/plotFact.ts
  frontend/src/types/foreshadowing.ts
  frontend/src/api/pendingMemory.ts
  frontend/src/stores/pendingMemory.ts
  frontend/src/views/novels/PendingConfirmView.vue

MODIFY:
  backend/.env.example              — add DEEPSEEK_API_KEY=
  backend/requirements.txt          — add langchain, langchain-deepseek, deepagents, python-dotenv
  backend/app/core/config.py        — add DEEPSEEK_API_KEY field
  backend/app/models/__init__.py    — export new models
  backend/tests/conftest.py         — add load_dotenv call before imports
  backend/app/main.py               — register ai router + import new models
  frontend/src/types/index.ts       — re-export new types
  frontend/src/router/index.ts      — add /novels/:id/pending route
  frontend/src/components/novels/NovelWorkspaceTabs.vue — add pending tab with badge
```

---

### Task 1: 依赖与环境配置

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Produces: `settings.DEEPSEEK_API_KEY` available globally

- [ ] **Step 1: 更新 requirements.txt**

```txt
# 在文件末尾追加
langchain==1.3.11
langchain-deepseek==1.1.0
deepagents>=1.0.0
python-dotenv>=1.0.0
```

- [ ] **Step 2: 更新 .env.example**

```
DEEPSEEK_API_KEY=
```

- [ ] **Step 3: 更新 config.py**

```python
# 在 Settings 类中新增
DEEPSEEK_API_KEY: str = ""
```

- [ ] **Step 4: 更新 conftest.py**

在 `os.environ` 设置块之前加入 dotenv 加载：

```python
from pathlib import Path
from dotenv import load_dotenv

dotenv_path = Path(__file__).resolve().parents[1] / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)

TEST_DB_PATH = Path(__file__).resolve().parents[1] / "test_novel_agent.db"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret-key"
```

- [ ] **Step 5: 安装依赖**

```bash
.venv/bin/pip install -r requirements.txt
```

- [ ] **Step 6: 验证配置可读**

```bash
.venv/bin/python -c "from app.core.config import settings; print('DEEPSEEK_API_KEY set:', bool(settings.DEEPSEEK_API_KEY))"
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: add AI dependencies and DEEPSEEK_API_KEY config"
```

---

### Task 2: 新增 ORM 模型 + Alembic 迁移

**Files:**
- Create: `backend/app/models/pending_memory.py`
- Create: `backend/app/models/plot_fact.py`
- Create: `backend/app/models/foreshadowing.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Produces: `PendingMemory`, `PlotFact`, `Foreshadowing` ORM classes

- [ ] **Step 1: 创建 PendingMemory 模型**

`backend/app/models/pending_memory.py`:

```python
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, JSON, func

from app.core.database import Base


class PendingMemory(Base):
    __tablename__ = "pending_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    memory_type = Column(String(50), nullable=False)  # character_change | plot_fact | world_setting | foreshadowing
    content = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending | confirmed | rejected
    created_at = Column(DateTime, nullable=False, default=func.now())
```

- [ ] **Step 2: 创建 PlotFact 模型**

`backend/app/models/plot_fact.py`:

```python
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON, func

from app.core.database import Base


class PlotFact(Base):
    __tablename__ = "plot_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    fact_type = Column(String(50), nullable=False)  # event | relationship | location | item | knowledge
    content = Column(Text, nullable=False)
    related_characters = Column(JSON, nullable=False, default=list)
    importance = Column(String(20), nullable=False, default="minor")  # major | minor
    created_at = Column(DateTime, nullable=False, default=func.now())
```

- [ ] **Step 3: 创建 Foreshadowing 模型**

`backend/app/models/foreshadowing.py`:

```python
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON, func

from app.core.database import Base


class Foreshadowing(Base):
    __tablename__ = "foreshadowings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    planted_chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    description = Column(Text, nullable=False)
    hidden_truth = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="planted")  # planted | developing | resolved
    expected_reveal_chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True)
    related_characters = Column(JSON, nullable=False, default=list)
    risk_warning = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: 更新 models/__init__.py**

```python
from app.models.foreshadowing import Foreshadowing
from app.models.memory import CharacterProfile, WorldSetting
from app.models.novel import Chapter, Novel
from app.models.pending_memory import PendingMemory
from app.models.plot_fact import PlotFact
from app.models.user import User

__all__ = [
    "User", "Novel", "Chapter",
    "CharacterProfile", "WorldSetting",
    "PendingMemory", "PlotFact", "Foreshadowing",
]
```

- [ ] **Step 5: 生成 Alembic 迁移**

```bash
.venv/bin/python -m alembic revision --autogenerate -m "phase_2_ai_memory_models"
```

- [ ] **Step 6: 验证迁移脚本生成并执行**

```bash
.venv/bin/python -m alembic upgrade head
```

检查数据库有三张新表: `pending_memories`, `plot_facts`, `foreshadowings`。

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: add PendingMemory, PlotFact, Foreshadowing ORM models"
```

---

### Task 3: AI 骨架 — Config + AgentState + Agent Factory

**Files:**
- Create: `backend/app/ai/__init__.py`
- Create: `backend/app/ai/config.py`
- Create: `backend/app/ai/models.py`
- Create: `backend/app/ai/agent.py`
- Create: `backend/app/ai/tools/__init__.py`
- Create: `backend/app/ai/middleware/__init__.py`

**Interfaces:**
- Produces: `FLASH_MODEL`, `PRO_MODEL` constants
- Produces: `NovelAgentState` class
- Produces: `create_novel_agent()`, `create_novel_deep_agent()` factory functions

- [ ] **Step 1: 创建 ai/__init__.py**

空文件。

- [ ] **Step 2: 创建 ai/config.py**

```python
FLASH_MODEL = "deepseek-v4-flash"
PRO_MODEL = "deepseek-v4-pro"
```

- [ ] **Step 3: 创建 ai/models.py**

```python
from langchain.agents import AgentState


class NovelAgentState(AgentState):
    novel_id: int = 0
    chapter_id: int = 0
    user_id: int = 0
    pending_confirmations: list[dict] = []
```

- [ ] **Step 4: 创建 ai/tools/__init__.py 和 ai/middleware/__init__.py**

两个空文件。

- [ ] **Step 5: 创建 ai/agent.py**

```python
from typing import Literal

from langchain.agents import AgentState, create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.ai.config import FLASH_MODEL, PRO_MODEL


def create_novel_agent(
    model_type: Literal["flash", "pro"] = "flash",
    tools: list[BaseTool] | None = None,
    system_prompt: str = "",
    state_schema: type[AgentState] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    model_name = FLASH_MODEL if model_type == "flash" else PRO_MODEL
    model = init_chat_model(model_name, model_provider="deepseek")
    return create_agent(
        model=model,
        tools=tools or [],
        system_prompt=system_prompt,
        state_schema=state_schema,
        checkpointer=checkpointer,
    )


def create_novel_deep_agent(
    tools: list[BaseTool] | None = None,
    system_prompt: str = "",
    state_schema: type[AgentState] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    model = init_chat_model(PRO_MODEL, model_provider="deepseek")
    try:
        from deepagents import create_deep_agent
    except ImportError:
        raise ImportError("deepagents package required for create_novel_deep_agent")
    return create_deep_agent(
        model=model,
        tools=tools or [],
        system_prompt=system_prompt,
        state_schema=state_schema,
        checkpointer=checkpointer,
    )
```

- [ ] **Step 6: 验证导入**

```bash
.venv/bin/python -c "from app.ai.agent import create_novel_agent, create_novel_deep_agent; print('AI agent factory loaded')"
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: add AI skeleton - config, state, agent factory"
```

---

### Task 4: Tools + Middleware

**Files:**
- Create: `backend/app/ai/tools/context.py`
- Create: `backend/app/ai/tools/memory.py`
- Create: `backend/app/ai/middleware/logging.py`

**Interfaces:**
- Produces: `get_chapter_context`, `save_character_changes`, `save_plot_facts`, `save_world_settings`, `save_foreshadowing_candidates` tools
- Produces: `logging_middleware` function

- [ ] **Step 1: 创建 context.py（读取工具）**

```python
import json

from langchain.tools import tool, ToolRuntime

from app.ai.models import NovelAgentState
from app.models.character_profile import CharacterProfile
from app.models.world_setting import WorldSetting
from app.models.foreshadowing import Foreshadowing
from app.models.plot_fact import PlotFact
from app.core.database import async_session_factory


@tool
async def get_chapter_context(
    novel_id: int,
    chapter_id: int,
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """获取章节全文、已有角色设定、世界观设定、伏笔信息和剧情事实"""
    async with async_session_factory() as db:
        from app.models.novel import Chapter
        result = await db.get(Chapter, chapter_id)
        if not result or result.novel_id != novel_id:
            return "章节不存在"

        chapter = result
        context_parts = [
            f"[章节标题]\n{chapter.title}",
            f"[章节正文]\n{chapter.content}",
        ]

        # 角色
        chars = await db.execute(
            CharacterProfile.__table__.select().where(CharacterProfile.novel_id == novel_id)
        )
        char_rows = chars.fetchall()
        if char_rows:
            parts = ["\n[已有角色]"]
            for c in char_rows:
                parts.append(f"{c['name']}: 身份={c['identity']}, 性格={c['personality']}, 当前状态={c['current_state']}")
            context_parts.append("\n".join(parts))

        # 世界观设定
        settings = await db.execute(
            WorldSetting.__table__.select().where(WorldSetting.novel_id == novel_id)
        )
        setting_rows = settings.fetchall()
        if setting_rows:
            parts = ["\n[已有设定]"]
            for s in setting_rows:
                parts.append(f"{s['title']} ({s['category']}): {s['content']}")
            context_parts.append("\n".join(parts))

        # 伏笔
        foreshadows = await db.execute(
            Foreshadowing.__table__.select().where(Foreshadowing.novel_id == novel_id)
        )
        foreshadow_rows = foreshadows.fetchall()
        if foreshadow_rows:
            parts = ["\n[已有伏笔]"]
            for f in foreshadow_rows:
                parts.append(f"{f['name']}: {f['description']} (状态={f['status']})")
            context_parts.append("\n".join(parts))

        # 剧情事实
        facts = await db.execute(
            PlotFact.__table__.select().where(PlotFact.novel_id == novel_id)
        )
        fact_rows = facts.fetchall()
        if fact_rows:
            parts = ["\n[已有剧情事实]"]
            for f in fact_rows:
                related = json.dumps(f['related_characters'], ensure_ascii=False)
                parts.append(f"{f['content']} (涉及: {related}, 重要性: {f['importance']})")
            context_parts.append("\n".join(parts))

    return "\n".join(context_parts)
```

- [ ] **Step 2: 创建 memory.py（写入工具）**

```python
from langchain.tools import tool, ToolRuntime

from app.ai.models import NovelAgentState


@tool
async def save_character_changes(
    changes: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录角色变化到待确认区。

    changes 格式: [{name, field, change_description, reason}]
    示例: [{name: "主角", field: "current_state", change_description: "得知身世真相后情绪崩溃", reason: "第5章揭露身世"}]
    """
    runtime.state["pending_confirmations"].append({
        "memory_type": "character_change",
        "data": changes,
    })
    return f"已记录 {len(changes)} 条角色变化，待用户确认"


@tool
async def save_plot_facts(
    facts: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录剧情事实到待确认区。

    facts 格式: [{event, characters_involved, importance, description}]
    """
    runtime.state["pending_confirmations"].append({
        "memory_type": "plot_fact",
        "data": facts,
    })
    return f"已记录 {len(facts)} 条剧情事实，待用户确认"


@tool
async def save_world_settings(
    settings: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录新世界观设定到待确认区。

    settings 格式: [{title, category, content}]
    category 可选: geography | faction | rule | history | culture | other
    """
    runtime.state["pending_confirmations"].append({
        "memory_type": "world_setting",
        "data": settings,
    })
    return f"已记录 {len(settings)} 条世界观设定，待用户确认"


@tool
async def save_foreshadowing_candidates(
    candidates: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录伏笔候选到待确认区。

    candidates 格式: [{name, description, hint, expected_reveal_after_chapter, related_characters}]
    """
    runtime.state["pending_confirmations"].append({
        "memory_type": "foreshadowing",
        "data": candidates,
    })
    return f"已记录 {len(candidates)} 条伏笔候选，待用户确认"
```

- [ ] **Step 3: 创建 middleware/logging.py**

```python
import logging
import time

from langchain.agents.middleware import wrap_model_call

logger = logging.getLogger("novel_agent.ai")


@wrap_model_call
async def logging_middleware(request, handler):
    """记录模型调用的耗时和基本信息"""
    start = time.time()
    response = await handler(request)
    elapsed = time.time() - start
    logger.info("Model call completed in %.2fs", elapsed)
    return response
```

- [ ] **Step 4: 验证导入**

```bash
.venv/bin/python -c "from app.ai.tools.context import get_chapter_context; from app.ai.tools.memory import save_character_changes; from app.ai.middleware.logging import logging_middleware; print('Tools and middleware loaded')"
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add AI tools and logging middleware"
```

---

### Task 5: Service + Router + PendingMemory Repository

**Files:**
- Create: `backend/app/repositories/pending_memory_repo.py`
- Create: `backend/app/schemas/pending_memory.py`
- Create: `backend/app/ai/service.py`
- Create: `backend/app/ai/router.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `POST /api/v1/novels/{novel_id}/chapters/{chapter_id}/extract`
- Produces: `GET /api/v1/novels/{novel_id}/pending-memories`
- Produces: `PUT /api/v1/novels/{novel_id}/pending-memories/{id}/confirm`
- Produces: `PUT /api/v1/novels/{novel_id}/pending-memories/{id}/reject`
- Produces: `PUT /api/v1/novels/{novel_id}/pending-memories/batch`

- [ ] **Step 1: 创建 schemas/pending_memory.py**

```python
from datetime import datetime

from pydantic import BaseModel


class PendingMemoryOut(BaseModel):
    id: int
    novel_id: int
    chapter_id: int
    memory_type: str
    content: dict
    status: str
    created_at: datetime


class PendingMemoryBatchBody(BaseModel):
    ids: list[int]
    action: str  # "confirm" | "reject"


class ExtractResponse(BaseModel):
    chapter_summary: str | None = None
    pending_ids: list[int] = []
    pending_count: int = 0


class ExtractRequest(BaseModel):
    mode: str = "standard"  # "standard" | "deep"
```

- [ ] **Step 2: 创建 repositories/pending_memory_repo.py**

```python
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pending_memory import PendingMemory
from app.models.character_profile import CharacterProfile
from app.models.world_setting import WorldSetting
from app.models.plot_fact import PlotFact
from app.models.foreshadowing import Foreshadowing
from app.core.database import async_session_factory


class PendingMemoryRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_novel(self, novel_id: int, status: str | None = None) -> list[PendingMemory]:
        stmt = select(PendingMemory).where(
            PendingMemory.novel_id == novel_id,
        ).order_by(PendingMemory.created_at.desc())
        if status:
            stmt = stmt.where(PendingMemory.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, memory_id: int) -> PendingMemory | None:
        return await self.db.get(PendingMemory, memory_id)

    async def create(self, novel_id: int, chapter_id: int, memory_type: str, content: dict) -> PendingMemory:
        pm = PendingMemory(
            novel_id=novel_id,
            chapter_id=chapter_id,
            memory_type=memory_type,
            content=content,
        )
        self.db.add(pm)
        await self.db.commit()
        await self.db.refresh(pm)
        return pm

    async def confirm(self, memory: PendingMemory) -> None:
        """确认 pending 记录，写入对应正式表。content.data 包含实际条目。"""
        memory.status = "confirmed"
        data_list = memory.content.get("data", [])
        if memory.memory_type == "character_change":
            for change in data_list:
                stmt = select(CharacterProfile).where(
                    CharacterProfile.novel_id == memory.novel_id,
                    CharacterProfile.name == change["name"],
                )
                result = await self.db.execute(stmt)
                char = result.scalar_one_or_none()
                if char and (field := change.get("field")):
                    if hasattr(char, field):
                        setattr(char, field, change["change_description"])
        elif memory.memory_type == "world_setting":
            for s in data_list:
                ws = WorldSetting(
                    novel_id=memory.novel_id,
                    title=s["title"],
                    category=s.get("category", "other"),
                    content=s.get("content", ""),
                )
                self.db.add(ws)
        elif memory.memory_type == "plot_fact":
            for f in data_list:
                pf = PlotFact(
                    novel_id=memory.novel_id,
                    chapter_id=memory.chapter_id,
                    fact_type=f.get("fact_type", "event"),
                    content=f.get("description", f.get("event", "")),
                    related_characters=f.get("characters_involved", []),
                    importance=f.get("importance", "minor"),
                )
                self.db.add(pf)
        elif memory.memory_type == "foreshadowing":
            for c in data_list:
                fs = Foreshadowing(
                    novel_id=memory.novel_id,
                    name=c["name"],
                    planted_chapter_id=memory.chapter_id,
                    description=c.get("description", ""),
                    hidden_truth=c.get("hint", ""),
                    related_characters=c.get("related_characters", []),
                )
                self.db.add(fs)
        await self.db.commit()

    async def reject(self, memory: PendingMemory) -> None:
        memory.status = "rejected"
        await self.db.commit()
```

- [ ] **Step 3: 创建 ai/service.py**

```python
import logging

from langgraph.checkpoint.memory import InMemorySaver

from app.ai.agent import create_novel_agent, create_novel_deep_agent
from app.ai.models import NovelAgentState
from app.ai.tools.context import get_chapter_context
from app.ai.tools.memory import (
    save_character_changes,
    save_plot_facts,
    save_world_settings,
    save_foreshadowing_candidates,
)
from app.ai.middleware.logging import logging_middleware
from app.repositories.pending_memory_repo import PendingMemoryRepo
from app.core.database import async_session_factory

logger = logging.getLogger("novel_agent.ai")

STANDARD_PROMPT = """你是一个小说创作辅助 Agent，负责分析章节内容并提取结构化信息。

## 工作流程
1. 使用 get_chapter_context 工具获取章节内容和相关记忆
2. 分析内容，提取以下信息：
   - 角色变化（性格、动机、状态、关系的变化）
   - 剧情事实（本章发生的重要事件）
   - 世界观设定（新出现的地点、组织、规则）
   - 伏笔候选（看似普通但可能重要的信息）
3. 使用对应的 save_* 工具写入提取结果

## 规则
- 只提取本章有明确依据的信息，不要臆测
- 角色变化要有原文支撑
- 伏笔候选标注潜在的回收方向
- 完成后回复"提取完成"并总结提取条目数"""

DEEP_PROMPT = STANDARD_PROMPT + """

## 深度分析要求
- 分析伏笔之间的隐含关联
- 评估章节内容与已有设定的冲突点
- 标记可能被忽略的细节（可能发展为后续情节）
- 对角色行为的合理性给出判断"""


class NovelExtractionService:
    def __init__(self):
        self.tools = [
            get_chapter_context,
            save_character_changes,
            save_plot_facts,
            save_world_settings,
            save_foreshadowing_candidates,
        ]
        self.checkpointer = InMemorySaver()

    async def extract(self, novel_id: int, chapter_id: int, user_id: int, mode: str = "standard") -> dict:
        state = NovelAgentState(
            novel_id=novel_id,
            chapter_id=chapter_id,
            user_id=user_id,
        )

        if mode == "deep":
            agent = create_novel_deep_agent(
                tools=self.tools,
                system_prompt=DEEP_PROMPT,
                state_schema=NovelAgentState,
                checkpointer=self.checkpointer,
            )
        else:
            agent = create_novel_agent(
                model_type="flash",
                tools=self.tools,
                system_prompt=STANDARD_PROMPT,
                state_schema=NovelAgentState,
                checkpointer=self.checkpointer,
            )

        result = await agent.ainvoke(
            {
                "messages": [
                    {"role": "user", "content": f"请分析 novel_id={novel_id} 的第 {chapter_id} 章，提取所有结构化信息。"}
                ],
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "user_id": user_id,
            },
            config={"configurable": {"thread_id": f"extract-{novel_id}-{chapter_id}"}},
        )

        final_state = result.get("state", state)

        # 将 pending_confirmations 写入数据库
        pending_ids = []
        async with async_session_factory() as db:
            repo = PendingMemoryRepo(db)
            for entry in final_state.pending_confirmations:
                pm = await repo.create(
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    memory_type=entry["memory_type"],
                    content=entry,
                )
                pending_ids.append(pm.id)

        # 从结果中提取章节摘要
        summary = None
        last_msg = result["messages"][-1] if result.get("messages") else None
        if last_msg and hasattr(last_msg, "content"):
            summary = last_msg.content

        return {
            "chapter_summary": summary,
            "pending_ids": pending_ids,
            "pending_count": len(pending_ids),
        }
```

- [ ] **Step 4: 创建 ai/router.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import NovelExtractionService
from app.core.database import get_db
from app.core.exceptions import NotFound
from app.core.response import ApiResponse
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.pending_memory_repo import PendingMemoryRepo
from app.schemas.pending_memory import (
    ExtractRequest,
    ExtractResponse,
    PendingMemoryBatchBody,
    PendingMemoryOut,
)
from app.services.novel_service import NovelService

router = APIRouter(prefix="/novels/{novel_id}", tags=["AI"])

extraction_service = NovelExtractionService()


@router.post("/chapters/{chapter_id}/extract")
async def extract_chapter(
    novel_id: int,
    chapter_id: int,
    body: ExtractRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).get(novel_id, current_user.id)
    result = await extraction_service.extract(
        novel_id=novel_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        mode=body.mode,
    )
    return ApiResponse.success(data=ExtractResponse(**result).model_dump())


@router.get("/pending-memories")
async def list_pending_memories(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).get(novel_id, current_user.id)
    repo = PendingMemoryRepo(db)
    memories = await repo.list_by_novel(novel_id)
    return ApiResponse.success(
        data=[PendingMemoryOut.model_validate(m) for m in memories]
    )


@router.put("/pending-memories/{memory_id}/confirm")
async def confirm_pending_memory(
    novel_id: int,
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).get(novel_id, current_user.id)
    repo = PendingMemoryRepo(db)
    memory = await repo.get(memory_id)
    if not memory or memory.novel_id != novel_id:
        raise NotFound("PendingMemory", memory_id)
    await repo.confirm(memory)
    return ApiResponse.success(message="已确认并写入正式记忆")


@router.put("/pending-memories/{memory_id}/reject")
async def reject_pending_memory(
    novel_id: int,
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).get(novel_id, current_user.id)
    repo = PendingMemoryRepo(db)
    memory = await repo.get(memory_id)
    if not memory or memory.novel_id != novel_id:
        raise NotFound("PendingMemory", memory_id)
    await repo.reject(memory)
    return ApiResponse.success(message="已拒绝")


@router.put("/pending-memories/batch")
async def batch_pending_memories(
    novel_id: int,
    body: PendingMemoryBatchBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).get(novel_id, current_user.id)
    repo = PendingMemoryRepo(db)
    for mid in body.ids:
        memory = await repo.get(mid)
        if memory and memory.novel_id == novel_id:
            if body.action == "confirm":
                await repo.confirm(memory)
            elif body.action == "reject":
                await repo.reject(memory)
    return ApiResponse.success(message=f"批量{body.action}完成")
```

- [ ] **Step 5: 在 main.py 注册 AI router + 导入新模型**

```python
# 在 import 块中追加
from app.models import PendingMemory, PlotFact, Foreshadowing  # noqa: F401

# 在 include_router 块中追加
from app.ai import router as ai_router
app.include_router(ai_router.router, prefix="/api/v1")
```

同时创建 `backend/app/ai/__init__.py` 并写入：
```python
from app.ai import router
```

- [ ] **Step 6: 验证启动**

```bash
.venv/bin/python -c "from app.main import app; print('App created with AI routes:', len([r for r in app.routes if hasattr(r, 'methods')]))"
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: add extraction service, pending memory API, and AI router"
```

---

### Task 6: 前端类型 + API 客户端 + Store

**Files:**
- Create: `frontend/src/types/pendingMemory.ts`
- Create: `frontend/src/types/plotFact.ts`
- Create: `frontend/src/types/foreshadowing.ts`
- Create: `frontend/src/api/pendingMemory.ts`
- Create: `frontend/src/stores/pendingMemory.ts`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 创建 types/pendingMemory.ts**

```typescript
export interface PendingMemory {
  id: number
  novel_id: number
  chapter_id: number
  memory_type: 'character_change' | 'plot_fact' | 'world_setting' | 'foreshadowing'
  content: Record<string, unknown>
  status: 'pending' | 'confirmed' | 'rejected'
  created_at: string
}

export interface ExtractRequest {
  mode: 'standard' | 'deep'
}

export interface ExtractResponse {
  chapter_summary: string | null
  pending_ids: number[]
  pending_count: number
}
```

- [ ] **Step 2: 创建 types/plotFact.ts**

```typescript
export interface PlotFact {
  id: number
  novel_id: number
  chapter_id: number
  fact_type: 'event' | 'relationship' | 'location' | 'item' | 'knowledge'
  content: string
  related_characters: string[]
  importance: 'major' | 'minor'
  created_at: string
}
```

- [ ] **Step 3: 创建 types/foreshadowing.ts**

```typescript
export interface Foreshadowing {
  id: number
  novel_id: number
  name: string
  planted_chapter_id: number
  description: string
  hidden_truth: string
  status: 'planted' | 'developing' | 'resolved'
  expected_reveal_chapter_id: number | null
  related_characters: string[]
  risk_warning: string
  created_at: string
  updated_at: string
}
```

- [ ] **Step 4: 更新 types/index.ts**

```typescript
export * from './api'
export * from './auth'
export * from './memory'
export * from './novel'
export * from './pendingMemory'
export * from './plotFact'
export * from './foreshadowing'
```

- [ ] **Step 5: 创建 api/pendingMemory.ts**

```typescript
import client from './client'
import type { ApiResponse, PendingMemory, ExtractRequest, ExtractResponse } from '@/types'

export async function extractChapter(
  novelId: number,
  chapterId: number,
  mode: 'standard' | 'deep' = 'standard',
): Promise<ExtractResponse> {
  const res = await client.post<ApiResponse<ExtractResponse>>(
    `/novels/${novelId}/chapters/${chapterId}/extract`,
    { mode } as ExtractRequest,
  )
  return res.data.data
}

export async function listPendingMemories(novelId: number): Promise<PendingMemory[]> {
  const res = await client.get<ApiResponse<PendingMemory[]>>(
    `/novels/${novelId}/pending-memories`,
  )
  return res.data.data
}

export async function confirmPendingMemory(novelId: number, memoryId: number): Promise<void> {
  await client.put(`/novels/${novelId}/pending-memories/${memoryId}/confirm`)
}

export async function rejectPendingMemory(novelId: number, memoryId: number): Promise<void> {
  await client.put(`/novels/${novelId}/pending-memories/${memoryId}/reject`)
}

export async function batchPendingMemories(
  novelId: number,
  ids: number[],
  action: 'confirm' | 'reject',
): Promise<void> {
  await client.put(`/novels/${novelId}/pending-memories/batch`, { ids, action })
}
```

- [ ] **Step 6: 创建 stores/pendingMemory.ts**

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { PendingMemory } from '@/types'
import * as api from '@/api/pendingMemory'

export const usePendingMemoryStore = defineStore('pendingMemory', () => {
  const memories = ref<PendingMemory[]>([])
  const loading = ref(false)

  const pendingCount = () => memories.value.filter(m => m.status === 'pending').length

  async function fetchMemories(novelId: number) {
    loading.value = true
    try {
      memories.value = await api.listPendingMemories(novelId)
    } finally {
      loading.value = false
    }
  }

  async function confirm(memoryId: number) {
    const item = memories.value.find(m => m.id === memoryId)
    if (!item) return
    await api.confirmPendingMemory(item.novel_id, memoryId)
    item.status = 'confirmed'
  }

  async function reject(memoryId: number) {
    const item = memories.value.find(m => m.id === memoryId)
    if (!item) return
    await api.rejectPendingMemory(item.novel_id, memoryId)
    item.status = 'rejected'
  }

  async function batchAction(ids: number[], action: 'confirm' | 'reject') {
    if (!ids.length) return
    const novelId = memories.value.find(m => ids.includes(m.id))?.novel_id
    if (!novelId) return
    await api.batchPendingMemories(novelId, ids, action)
    memories.value.forEach(m => {
      if (ids.includes(m.id)) m.status = action === 'confirm' ? 'confirmed' : 'rejected'
    })
  }

  async function extract(novelId: number, chapterId: number, mode: 'standard' | 'deep' = 'standard') {
    return await api.extractChapter(novelId, chapterId, mode)
  }

  return { memories, loading, pendingCount, fetchMemories, confirm, reject, batchAction, extract }
})
```

- [ ] **Step 7: 验证类型编译**

```bash
npm run type-check
```

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: add frontend types, API client, and store for pending memories"
```

---

### Task 7: 前端 PendingConfirmView + 路由 + 标签

**Files:**
- Create: `frontend/src/views/novels/PendingConfirmView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/novels/NovelWorkspaceTabs.vue`

- [ ] **Step 1: 创建 PendingConfirmView.vue**

```vue
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePendingMemoryStore } from '@/stores/pendingMemory'

const route = useRoute()
const store = usePendingMemoryStore()
const novelId = Number(route.params.id)

const memoryLabels: Record<string, string> = {
  character_change: '角色变化',
  plot_fact: '剧情事实',
  world_setting: '世界观设定',
  foreshadowing: '伏笔候选',
}

const statusLabels: Record<string, string> = {
  pending: '待确认',
  confirmed: '已确认',
  rejected: '已拒绝',
}

const statusTypes: Record<string, string> = {
  pending: 'warning',
  confirmed: 'success',
  rejected: 'info',
}

const grouped = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const m of store.memories) {
    const key = memoryLabels[m.memory_type] || m.memory_type
    if (!groups[key]) groups[key] = []
    groups[key].push(m)
  }
  return groups
})

const pendingIds = computed(() =>
  store.memories.filter(m => m.status === 'pending').map(m => m.id),
)

async function handleConfirm(id: number) {
  await store.confirm(id)
  ElMessage.success('已确认')
}

async function handleReject(id: number) {
  await store.reject(id)
  ElMessage.success('已拒绝')
}

async function handleBatch(action: 'confirm' | 'reject') {
  if (!pendingIds.value.length) {
    ElMessage.info('没有待确认的条目')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定${action === 'confirm' ? '确认' : '拒绝'}全部 ${pendingIds.value.length} 条待确认条目？`,
      '提示',
    )
    await store.batchAction(pendingIds.value, action)
    ElMessage.success('操作完成')
  } catch { /* cancelled */ }
}

onMounted(() => store.fetchMemories(novelId))
</script>

<template>
  <div class="pending-confirm">
    <div class="page-header">
      <h2>待确认记忆</h2>
      <div v-if="pendingIds.length" class="batch-actions">
        <el-button type="primary" @click="handleBatch('confirm')">
          确认全部 ({{ pendingIds.length }})
        </el-button>
        <el-button @click="handleBatch('reject')">
          拒绝全部 ({{ pendingIds.length }})
        </el-button>
      </div>
    </div>

    <div v-if="store.loading" v-loading="store.loading" class="loading-wrap" />

    <div v-else-if="!store.memories.length" class="empty">
      <el-empty description="暂无待确认记忆" />
    </div>

    <div v-else v-for="(items, type) in grouped" :key="type" class="memory-group">
      <h3 class="group-title">{{ type }} ({{ items.length }})</h3>
      <el-card v-for="item in items" :key="item.id" class="memory-card" :class="item.status">
        <div class="card-header">
          <el-tag :type="statusTypes[item.status] as any" size="small">
            {{ statusLabels[item.status] }}
          </el-tag>
          <span class="card-time">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</span>
        </div>
        <pre class="card-content">{{ JSON.stringify(item.content, null, 2) }}</pre>
        <div v-if="item.status === 'pending'" class="card-actions">
          <el-button type="primary" size="small" @click="handleConfirm(item.id)">确认</el-button>
          <el-button size="small" @click="handleReject(item.id)">拒绝</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped lang="scss">
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.memory-group {
  margin-bottom: 24px;
}
.group-title {
  margin-bottom: 12px;
  font-size: 16px;
  color: var(--el-text-color-primary);
}
.memory-card {
  margin-bottom: 12px;
  &.confirmed { opacity: 0.7; }
  &.rejected { opacity: 0.5; }
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.card-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.card-content {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
}
.card-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
.loading-wrap {
  min-height: 200px;
}
.empty {
  padding: 60px 0;
}
</style>
```

- [ ] **Step 2: 更新 router/index.ts**

```typescript
// 在 children 数组中新增
{ path: 'novels/:id/pending', name: 'novel-pending', component: () => import('@/views/novels/PendingConfirmView.vue'), meta: { auth: true } },
```

- [ ] **Step 3: 更新 NovelWorkspaceTabs.vue**

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { TabPaneName } from 'element-plus'
import { usePendingMemoryStore } from '@/stores/pendingMemory'

const props = defineProps<{ novelId: number }>()
const route = useRoute()
const router = useRouter()
const store = usePendingMemoryStore()

const pendingBadge = computed(() => {
  const count = store.pendingCount()
  return count > 0 ? count : undefined
})

const tabs = computed(() => [
  { label: '章节', path: `/novels/${props.novelId}` },
  { label: '角色', path: `/novels/${props.novelId}/characters` },
  { label: '设定', path: `/novels/${props.novelId}/settings` },
  { label: () => '待确认', path: `/novels/${props.novelId}/pending`, badge: pendingBadge.value },
])

onMounted(() => { store.fetchMemories(props.novelId) })
</script>

<template>
  <el-tabs :model-value="route.path" @tab-change="(p: TabPaneName) => router.push(p as string)" class="workspace-tabs">
    <el-tab-pane v-for="tab in tabs" :key="tab.path" :label="tab.label" :name="tab.path">
      <template #label>
        <span>
          {{ tab.label }}
          <el-badge v-if="tab.badge" :value="tab.badge" :hidden="!tab.badge" />
        </span>
      </template>
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped lang="scss">
.workspace-tabs { margin-bottom: 16px; }
</style>
```

- [ ] **Step 4: 验证前端编译**

```bash
npm run type-check && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add PendingConfirmView and workspace tab with badge"
```

---

### Task 8: AI 集成测试

**Files:**
- Create: `backend/tests/test_phase_2_ai_extract.py`

- [ ] **Step 1: 创建测试文件**

```python
"""Phase 2 AI 提取集成测试——调用真实 DeepSeek API。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


pytestmark = pytest.mark.skipif(
    not settings.DEEPSEEK_API_KEY,
    reason="DEEPSEEK_API_KEY not set — set in .env to run AI tests",
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """注册并登录，返回 Authorization header。"""
    await client.post("/api/v1/auth/register", json={"username": "test_ai", "password": "pass123"})
    resp = await client.post("/api/v1/auth/login", json={"username": "test_ai", "password": "pass123"})
    token = resp.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def novel_chapter(client: AsyncClient, auth_headers: dict) -> tuple[int, int]:
    """创建测试小说和章节，返回 (novel_id, chapter_id)。"""
    resp = await client.post("/api/v1/novels", json={"title": "AI测试小说"}, headers=auth_headers)
    novel_id = resp.json()["data"]["id"]

    # 创建角色
    await client.post(f"/api/v1/novels/{novel_id}/characters", json={
        "name": "主角",
        "story_role": "protagonist",
        "personality": "冷静谨慎，重情义",
        "current_state": "离家出走中",
    }, headers=auth_headers)

    # 创建设定
    await client.post(f"/api/v1/novels/{novel_id}/settings", json={
        "title": "青云城",
        "category": "geography",
        "content": "边境要塞城市，常年风雪",
    }, headers=auth_headers)

    # 创建章节
    resp = await client.post(f"/api/v1/novels/{novel_id}/chapters", json={
        "title": "第一章 风雪夜归人",
        "content": (
            "青云城的冬天格外漫长。主角裹紧了大氅，在城门口遇到了一个受伤的陌生人。"
            "那人脸色苍白，胸前一道深可见骨的伤口还在渗血。"
            "主角犹豫了片刻，还是把他扶进了城中唯一的客栈。"
            "客栈老板娘认得主角，惊讶地问：'你怎么回来了？'"
            "主角没有回答。他盯着陌生人腰间那枚玉佩，瞳孔微缩——"
            "那是他十年前送给妹妹的信物。"
        ),
    }, headers=auth_headers)
    chapter_id = resp.json()["data"]["id"]
    return novel_id, chapter_id


@pytest.mark.asyncio
async def test_extract_chapter_basic(client: AsyncClient, auth_headers: dict, novel_chapter: tuple[int, int]):
    """测试标准模式提取——验证返回结构正确。"""
    novel_id, chapter_id = novel_chapter
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/extract",
        json={"mode": "standard"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    extract = data["data"]
    assert "pending_ids" in extract
    assert "pending_count" in extract
    assert extract["pending_count"] == len(extract["pending_ids"])


@pytest.mark.asyncio
async def test_extract_chapter_deep(client: AsyncClient, auth_headers: dict, novel_chapter: tuple[int, int]):
    """测试深度模式提取。"""
    novel_id, chapter_id = novel_chapter
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/extract",
        json={"mode": "deep"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0


@pytest.mark.asyncio
async def test_pending_memory_confirm_flow(client: AsyncClient, auth_headers: dict, novel_chapter: tuple[int, int]):
    """测试完整流程：提取 → 查看待确认 → 确认 → 拒绝。"""
    novel_id, chapter_id = novel_chapter

    # 提取
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/extract",
        json={"mode": "standard"},
        headers=auth_headers,
    )
    pending_ids = resp.json()["data"]["pending_ids"]
    assert len(pending_ids) > 0

    # 查看待确认列表
    resp = await client.get(f"/api/v1/novels/{novel_id}/pending-memories", headers=auth_headers)
    assert resp.status_code == 200
    memories = resp.json()["data"]
    assert len(memories) >= len(pending_ids)

    # 确认第一条
    first_id = pending_ids[0]
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/pending-memories/{first_id}/confirm",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # 拒绝第二条
    if len(pending_ids) > 1:
        second_id = pending_ids[1]
        resp = await client.put(
            f"/api/v1/novels/{novel_id}/pending-memories/{second_id}/reject",
            headers=auth_headers,
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pending_memory_batch(client: AsyncClient, auth_headers: dict, novel_chapter: tuple[int, int]):
    """测试批量操作。"""
    novel_id, chapter_id = novel_chapter

    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/extract",
        json={"mode": "standard"},
        headers=auth_headers,
    )
    pending_ids = resp.json()["data"]["pending_ids"]
    if not pending_ids:
        pytest.skip("No pending memories created")

    resp = await client.put(
        f"/api/v1/novels/{novel_id}/pending-memories/batch",
        json={"ids": pending_ids, "action": "confirm"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_extract_unauthorized(client: AsyncClient, novel_chapter: tuple[int, int]):
    """未认证用户不能调用提取。"""
    novel_id, chapter_id = novel_chapter
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/extract",
        json={"mode": "standard"},
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: 填写 DEEPSEEK_API_KEY 并运行测试**

```bash
# 先提醒用户填写 .env 中的 DEEPSEEK_API_KEY
echo "请在 backend/.env 中填入 DEEPSEEK_API_KEY=your_key_here"
```

用户填写后运行：

```bash
.venv/bin/python -m pytest tests/test_phase_2_ai_extract.py -x -q -v
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "test: add AI integration tests for extraction pipeline"
```
