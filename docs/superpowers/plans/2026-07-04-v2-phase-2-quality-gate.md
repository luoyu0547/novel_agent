# v2 Phase 2: Chapter Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automated quality gate to the writing pipeline that checks drafts for issues, auto-fixes what it can, and escalates creative choices to the user via an editor sidebar.

**Architecture:** 6 parallel AI agents check different quality dimensions; results split into auto-fixable (applied automatically, logged to `RepairLog`) and needs-intent (stored as `PendingRepair`, shown in editor sidebar for user interaction). A `FakeQualityGateAgent` enables testability without a real AI backend.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Vue 3 + Element Plus

**Global Constraints**
- Follow existing layer flow: `api/ → services/ → repositories/ → models/`
- All new routes mount under `/api/v1/novels/{novel_id}/`
- Use `ApiResponse.success()` / `ApiResponse.error()` for all responses
- All ORM models inherit from `app.core.database.Base`
- Schemas use Pydantic v2 `model_config = {"from_attributes": True}`
- Frontend components use existing SCSS variables (`@use '@/styles/variables' as *`)
- Element Plus components auto-imported; no manual `import` needed
- New Vue files use `<script setup lang="ts">` Composition API

---

### Task 1: Quality Gate Models + WritingRun Extension

**Files:**
- Modify: `backend/app/models/writing.py`
- Test: `backend/tests/test_phase_2_quality_gate.py`
- Export: `backend/app/models/__init__.py`

**Interfaces:**
- Consumes: existing `WritingRun` model
- Produces: `RepairLog`, `PendingRepair` ORM models; `WritingRun.gated`, `WritingRun.has_pending_repairs` fields

- [ ] **Step 1: Write the failing model tests**

```python
"""backend/tests/test_phase_2_quality_gate.py"""
import pytest
from sqlalchemy import select

from app.models.writing import RepairLog, PendingRepair, WritingRun


@pytest.mark.asyncio
async def test_repair_log_creation(db):
    """RepairLog 可以创建和读取。"""
    log = RepairLog(
        novel_id=1,
        writing_run_id=1,
        issue_type="character",
        description="人设修正",
        location="第2段",
        old_text="原文本摘要",
        new_text="新文本摘要",
    )
    db.add(log)
    await db.flush()
    result = await db.get(RepairLog, log.id)
    assert result is not None
    assert result.issue_type == "character"


@pytest.mark.asyncio
async def test_pending_repair_creation(db):
    """PendingRepair 可以创建和读取。"""
    repair = PendingRepair(
        novel_id=1,
        chapter_id=1,
        writing_run_id=1,
        issue_type="character_choice",
        description="角色抉择方向",
        location="第3段",
        context="角色面临抉择的原文片段",
        options=[{"label": "方案A", "summary": "角色表现果断"}, {"label": "方案B", "summary": "角色表现犹豫"}],
        intent_type="choice",
        status="pending",
    )
    db.add(repair)
    await db.flush()
    result = await db.get(PendingRepair, repair.id)
    assert result is not None
    assert result.intent_type == "choice"
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_writing_run_has_gate_fields(db):
    """WritingRun 新增 gated 和 has_pending_repairs 字段。"""
    run = WritingRun(
        novel_id=1,
        chapter_brief_id=1,
        context_package_id=1,
        status="completed",
        draft_content="test",
        word_count=4,
        gated=True,
        has_pending_repairs=False,
    )
    db.add(run)
    await db.flush()
    result = await db.get(WritingRun, run.id)
    assert result.gated is True
    assert result.has_pending_repairs is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest backend/tests/test_phase_2_quality_gate.py -x -q`
Expected: FAIL — `RepairLog`, `PendingRepair` not defined, `WritingRun` has no `gated` field

- [ ] **Step 3: Add models to `backend/app/models/writing.py`**

Append after the `WritingRun` class:

```python
class RepairLog(Base):
    __tablename__ = "repair_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    writing_run_id: Mapped[int] = mapped_column(ForeignKey("writing_runs.id"), nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(Text, nullable=False, default="")
    old_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    new_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)


class PendingRepair(Base):
    __tablename__ = "pending_repairs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), nullable=False)
    writing_run_id: Mapped[int] = mapped_column(ForeignKey("writing_runs.id"), nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(Text, nullable=False, default="")
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    intent_type: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="pending")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
```

Add `gated` and `has_pending_repairs` to `WritingRun`:

```python
class WritingRun(Base):
    # ... existing fields unchanged ...
    gated: Mapped[bool] = mapped_column(default=False)
    has_pending_repairs: Mapped[bool] = mapped_column(default=False)
```

Update `app/models/__init__.py` to export `RepairLog`, `PendingRepair`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests/test_phase_2_quality_gate.py -x -q`
Expected: PASS

- [ ] **Step 5: Generate Alembic migration**

Run: `.venv/bin/python -m alembic revision --autogenerate -m "add repair_log and pending_repair tables"`
Expected: Migration file created with `repair_logs`, `pending_repairs` tables and `writing_runs.gated`, `writing_runs.has_pending_repairs` columns

Run: `.venv/bin/python -m alembic upgrade head`
Expected: Tables created

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add RepairLog, PendingRepair models and WritingRun gate fields"
```

---

### Task 2: Quality Gate Schemas

**Files:**
- Modify: `backend/app/schemas/writing.py`
- Test: already covered by Task 1 tests

**Interfaces:**
- Produces: `RepairLogOut`, `PendingRepairOut`, `ResolveRepairRequest`, `RepairsResponse` Pydantic models

- [ ] **Step 1: Add schemas to `backend/app/schemas/writing.py`**

```python
class RepairLogOut(BaseModel):
    id: int
    novel_id: int
    writing_run_id: int
    issue_type: str
    description: str
    location: str
    old_text: str
    new_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PendingRepairOut(BaseModel):
    id: int
    novel_id: int
    chapter_id: int
    writing_run_id: int
    issue_type: str
    description: str
    location: str
    context: str
    options: Optional[list] = None
    intent_type: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResolveRepairRequest(BaseModel):
    action: str = Field(...)  # "apply"
    choice_index: Optional[int] = None
    intent_text: Optional[str] = None


class RepairsResponse(BaseModel):
    repair_logs: list[RepairLogOut]
    pending_repairs: list[PendingRepairOut]
```

- [ ] **Step 2: Verify schemas work**

Run: `.venv/bin/python -c "from app.schemas.writing import RepairLogOut, PendingRepairOut, ResolveRepairRequest; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/writing.py
git commit -m "feat: add quality gate schemas (RepairLog, PendingRepair)"
```

---

### Task 3: Quality Gate Repositories

**Files:**
- Create: `backend/app/repositories/quality_gate_repo.py`
- Test: `backend/tests/test_phase_2_quality_gate.py`

**Interfaces:**
- Produces: `RepairLogRepo`, `PendingRepairRepo` classes following same patterns as `WritingRunRepo`

- [ ] **Step 1: Write the failing repo tests**

```python
"""Add to backend/tests/test_phase_2_quality_gate.py"""
from app.repositories.quality_gate_repo import RepairLogRepo, PendingRepairRepo

@pytest.mark.asyncio
async def test_repair_log_repo_create_and_list(db):
    repo = RepairLogRepo(db)
    log = await repo.create(1, 1, {
        "issue_type": "style",
        "description": "风格修复",
        "location": "第1段",
        "old_text": "旧文本",
        "new_text": "新文本",
    })
    assert log.id is not None
    logs = await repo.list_by_writing_run(1)
    assert len(logs) == 1
    assert logs[0].issue_type == "style"


@pytest.mark.asyncio
async def test_pending_repair_repo_create_and_list(db):
    repo = PendingRepairRepo(db)
    repair = await repo.create(1, 1, 1, {
        "issue_type": "character_choice",
        "description": "角色选择",
        "location": "第3段",
        "context": "原文",
        "options": [{"label": "A", "summary": "方案A"}],
        "intent_type": "choice",
    })
    assert repair.id is not None
    repairs = await repo.list_pending_by_writing_run(1)
    assert len(repairs) == 1
    assert repairs[0].status == "pending"


@pytest.mark.asyncio
async def test_pending_repair_update_status(db):
    repo = PendingRepairRepo(db)
    repair = await repo.create(1, 1, 1, {
        "issue_type": "character_choice",
        "description": "角色选择",
        "location": "第3段",
        "context": "原文",
        "intent_type": "choice",
    })
    updated = await repo.update_status(repair.id, "applied")
    assert updated.status == "applied"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest backend/tests/test_phase_2_quality_gate.py -x -q`
Expected: FAIL — `RepairLogRepo` not found

- [ ] **Step 3: Create `backend/app/repositories/quality_gate_repo.py`**

```python
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.writing import RepairLog, PendingRepair


class RepairLogRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, novel_id: int, writing_run_id: int, data: dict) -> RepairLog:
        log = RepairLog(novel_id=novel_id, writing_run_id=writing_run_id, **data)
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_by_writing_run(self, writing_run_id: int) -> list[RepairLog]:
        result = await self.db.execute(
            select(RepairLog)
            .where(RepairLog.writing_run_id == writing_run_id)
            .order_by(RepairLog.created_at.asc())
        )
        return list(result.scalars().all())

    async def cleanup_by_writing_run(self, writing_run_id: int):
        logs = await self.list_by_writing_run(writing_run_id)
        for log in logs:
            await self.db.delete(log)
        await self.db.flush()


class PendingRepairRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, novel_id: int, chapter_id: int, writing_run_id: int, data: dict) -> PendingRepair:
        repair = PendingRepair(novel_id=novel_id, chapter_id=chapter_id, writing_run_id=writing_run_id, **data)
        self.db.add(repair)
        await self.db.flush()
        return repair

    async def get_by_id(self, repair_id: int) -> Optional[PendingRepair]:
        return await self.db.get(PendingRepair, repair_id)

    async def list_by_writing_run(self, writing_run_id: int) -> list[PendingRepair]:
        result = await self.db.execute(
            select(PendingRepair)
            .where(PendingRepair.writing_run_id == writing_run_id)
            .order_by(PendingRepair.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_pending_by_writing_run(self, writing_run_id: int) -> list[PendingRepair]:
        result = await self.db.execute(
            select(PendingRepair)
            .where(PendingRepair.writing_run_id == writing_run_id, PendingRepair.status == "pending")
            .order_by(PendingRepair.created_at.asc())
        )
        return list(result.scalars().all())

    async def update_status(self, repair_id: int, status: str) -> PendingRepair:
        repair = await self.get_by_id(repair_id)
        if repair:
            repair.status = status
            await self.db.flush()
        return repair

    async def cleanup_by_writing_run(self, writing_run_id: int):
        repairs = await self.list_by_writing_run(writing_run_id)
        for r in repairs:
            await self.db.delete(r)
        await self.db.flush()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests/test_phase_2_quality_gate.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/quality_gate_repo.py backend/tests/test_phase_2_quality_gate.py
git commit -m "feat: add RepairLogRepo and PendingRepairRepo"
```

---

### Task 4: Fake Quality Gate Agent (Testability)

**Files:**
- Create: `backend/app/ai/quality_gate.py`
- Test: `backend/tests/test_phase_2_quality_gate.py`

**Interfaces:**
- Produces: `BaseQualityGateAgent` (interface), `FakeQualityGateAgent` (for tests), `CheckResult` (Pydantic model), `CheckAgent` (named tuple or enum)

- [ ] **Step 1: Write the failing test**

```python
"""Add to backend/tests/test_phase_2_quality_gate.py"""
from app.ai.quality_gate import FakeQualityGateAgent, CheckResult

@pytest.mark.asyncio
async def test_fake_quality_gate_returns_all_passed():
    agent = FakeQualityGateAgent()
    results = await agent.check("draft content", {}, {})
    assert isinstance(results, list)
    assert len(results) == 6
    for r in results:
        assert r.passed is True
        assert r.severity == "auto_fixable"


@pytest.mark.asyncio
async def test_fake_quality_gate_with_story_data():
    agent = FakeQualityGateAgent()
    brief = {"plot_task": "主角发现真相"}
    context = {"characters": [{"name": "张三", "personality": "谨慎"}]}
    results = await agent.check("故事正文内容", brief, context)
    assert all(r.passed for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest backend/tests/test_phase_2_quality_gate.py -x -q`
Expected: FAIL

- [ ] **Step 3: Create `backend/app/ai/quality_gate.py`**

```python
import abc
from typing import Optional

from pydantic import BaseModel


class CheckResult(BaseModel):
    passed: bool
    issue_type: str
    severity: str  # "auto_fixable" | "needs_intent"
    fix_strategy: Optional[str] = None  # "full_rewrite" | "local_replace" | None
    fixed_text: Optional[str] = None
    fix_description: str = ""
    options: Optional[list[dict]] = None
    intent_type: Optional[str] = None
    description: str = ""
    location: str = ""
    context: str = ""


AGENT_TYPES = [
    "task_completion",
    "style",
    "character",
    "continuity",
    "world",
    "foreshadowing",
    "length",
]


class BaseQualityGateAgent(abc.ABC):
    @abc.abstractmethod
    async def check(self, draft: str, brief: dict, context_package: dict) -> list[CheckResult]:
        ...


class FakeQualityGateAgent(BaseQualityGateAgent):
    async def check(self, draft: str, brief: dict, context_package: dict) -> list[CheckResult]:
        return [
            CheckResult(passed=True, issue_type=t, severity="auto_fixable", fix_strategy="local_replace")
            for t in AGENT_TYPES
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest backend/tests/test_phase_2_quality_gate.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/quality_gate.py backend/tests/test_phase_2_quality_gate.py
git commit -m "feat: add BaseQualityGateAgent and FakeQualityGateAgent"
```

---

### Task 5: Quality Gate Service

**Files:**
- Create: `backend/app/services/quality_gate_service.py`
- Test: `backend/tests/test_phase_2_quality_gate.py`

**Interfaces:**
- Consumes: `BaseQualityGateAgent` (interface, injected), `RepairLogRepo`, `PendingRepairRepo`, `WritingRunRepo`
- Produces: `QualityGateService.run()` — orchestrates check, auto-fix, pending-repair creation

- [ ] **Step 1: Write the failing service tests**

```python
"""Add to backend/tests/test_phase_2_quality_gate.py"""
from app.services.quality_gate_service import QualityGateService
from app.ai.quality_gate import FakeQualityGateAgent
from app.repositories.quality_gate_repo import RepairLogRepo, PendingRepairRepo

@pytest.mark.asyncio
async def test_quality_gate_service_all_pass(db):
    """全部通过时，不产生 RepairLog 和 PendingRepair。"""
    from app.models.writing import WritingRun
    run = WritingRun(novel_id=1, chapter_brief_id=1, context_package_id=1, status="running", draft_content="test", word_count=4)
    db.add(run)
    await db.flush()
    svc = QualityGateService(db=db, agent=FakeQualityGateAgent())
    result = await svc.run(run, {}, {})
    assert result["gated"] is True
    assert result["has_pending_repairs"] is False
    logs_repo = RepairLogRepo(db)
    logs = await logs_repo.list_by_writing_run(run.id)
    assert len(logs) == 0
    pend_repo = PendingRepairRepo(db)
    repairs = await pend_repo.list_by_writing_run(run.id)
    assert len(repairs) == 0
    await db.rollback()


@pytest.mark.asyncio
async def test_quality_gate_service_no_agent(db):
    """不传 agent 时使用 FakeQualityGateAgent（默认行为）。"""
    from app.models.writing import WritingRun
    run = WritingRun(novel_id=1, chapter_brief_id=1, context_package_id=1, status="running", draft_content="test", word_count=4)
    db.add(run)
    await db.flush()
    svc = QualityGateService(db=db)
    result = await svc.run(run, {}, {})
    assert result["gated"] is True
    await db.rollback()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest backend/tests/test_phase_2_quality_gate.py -x -q`
Expected: FAIL — `QualityGateService` not defined

- [ ] **Step 3: Create `backend/app/services/quality_gate_service.py`**

```python
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
            return {"gated": False, "has_pending_repairs": False}

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests/test_phase_2_quality_gate.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/quality_gate_service.py backend/tests/test_phase_2_quality_gate.py
git commit -m "feat: add QualityGateService"
```

---

### Task 6: Integrate Quality Gate into WritingService

**Files:**
- Modify: `backend/app/services/writing_service.py`

**Interfaces:**
- Modifies: `WritingService.create_writing_run()` — calls `QualityGateService.run()` after draft generation
- Add "pending_rewrite" status handling for `accept_writing_run` and `discard_writing_run`

- [ ] **Step 1: Modify `backend/app/services/writing_service.py`**

Add import:
```python
from app.services.quality_gate_service import QualityGateService
from app.ai.quality_gate import FakeQualityGateAgent, BaseQualityGateAgent
```

Modify `__init__`:
```python
def __init__(
    self,
    db: AsyncSession,
    user_id: int,
    novel_id: int,
    generator: Optional[BaseWritingGenerator] = None,
    gate_agent: Optional[BaseQualityGateAgent] = None,
):
    # ... existing init code ...
    self.gate_agent = gate_agent
```

Modify `create_writing_run` — add quality gate after success, including auto-fix retry loop:

The quality gate runs after word count gate passes. If it finds auto-fixable issues with `full_rewrite` strategy, it feeds the feedback back into `generate_draft` for a retry (same pattern as the word count gate). This loop runs at most 3 times to prevent infinite loops.

```python
async def create_writing_run(self, brief_id: int, context_package_id: Optional[int] = None) -> WritingRun:
    novel = await self._ensure_owned_novel()
    brief = await self.brief_repo.get_by_id(brief_id)
    if not brief or brief.novel_id != self.novel_id:
        raise NotFound("章节任务书不存在")
    if context_package_id:
        context_package = await self.context_repo.get_by_id(context_package_id)
        if not context_package or context_package.novel_id != self.novel_id:
            raise NotFound("上下文包不存在")
        package = context_package.package_json
    else:
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
        for retry in range(3):
            gate_svc_result = await gate_svc.run(run, brief.brief_json, package)
            if gate_svc_result.get("rewrite_needed"):
                package_with_feedback = dict(package)
                feedback = await self._collect_gate_feedback(run.id)
                package_with_feedback["gate_feedback"] = feedback
                draft = await self.generator.generate_draft(package_with_feedback)
                word_count = self._count_words(draft)
                run.draft_content = draft
                run.word_count = word_count
                run.gate_result_json = {"passed": True}
            else:
                break
        # ---

        run = await self.run_repo.update(run, {
            "draft_content": draft,
            "word_count": word_count,
            "gate_result_json": gate_result,
            "gated": gate_svc_result["gated"],
            "has_pending_repairs": gate_svc_result["has_pending_repairs"],
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


async def _collect_gate_feedback(self, run_id: int) -> str:
    """Collect RepairLog descriptions from the current run as feedback text."""
    from app.repositories.quality_gate_repo import RepairLogRepo
    log_repo = RepairLogRepo(self.db)
    logs = await log_repo.list_by_writing_run(run_id)
    return "；".join(l.description for l in logs if l.description)
```

Modify `get_writing_run` to include repair data in response (add new method):
```python
async def get_writing_run_with_repairs(self, run_id: int) -> dict:
    run = await self.get_writing_run(run_id)
    from app.repositories.quality_gate_repo import RepairLogRepo, PendingRepairRepo
    log_repo = RepairLogRepo(self.db)
    pending_repo = PendingRepairRepo(self.db)
    logs = await log_repo.list_by_writing_run(run_id)
    pending = await pending_repo.list_by_writing_run(run_id)
    return {"run": run, "repair_logs": logs, "pending_repairs": pending}
```

- [ ] **Step 2: Write integration test**

```python
"""Add to backend/tests/test_phase_2_quality_gate.py"""
@pytest.mark.asyncio
async def test_quality_gate_in_writing_flow(client, novel_and_headers):
    """写作流程中质量门禁自动执行。"""
    novel, headers = novel_and_headers
    novel_id = novel["id"]

    # Generate blueprint
    bp_resp = await client.post(
        f"/api/v1/novels/{novel_id}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    bp_id = bp_resp.json()["data"]["id"]
    await client.put(f"/api/v1/novels/{novel_id}/blueprints/{bp_id}/activate", headers=headers)

    # Generate chapter plan
    plan_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-plans/next/generate",
        headers=headers,
    )
    plan_id = plan_resp.json()["data"]["id"]

    # Generate chapter brief
    brief_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-briefs/generate",
        headers=headers,
        json={"chapter_plan_id": plan_id},
    )
    brief_id = brief_resp.json()["data"]["id"]

    # Create writing run
    run_resp = await client.post(
        f"/api/v1/novels/{novel_id}/writing-runs",
        headers=headers,
        json={"chapter_brief_id": brief_id},
    )
    assert run_resp.status_code == 200
    run = run_resp.json()["data"]
    assert "gated" in run
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest backend/tests/test_phase_2_quality_gate.py tests/test_phase_1_writing.py -x -q`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/writing_service.py backend/tests/test_phase_2_quality_gate.py
git commit -m "feat: integrate quality gate into WritingService"
```

---

### Task 7: Quality Gate Router Endpoints

**Files:**
- Modify: `backend/app/api/writing.py`
- Test: `backend/tests/test_phase_2_quality_gate.py`

**Interfaces:**
- Produces: `GET /api/v1/novels/{novel_id}/writing-runs/{run_id}/repairs` (list all repairs)
- Accepts: `PUT /api/v1/novels/{novel_id}/writing/repairs/{repair_id}/resolve` (resolve a pending repair)

- [ ] **Step 1: Write failing router tests**

```python
"""Add to backend/tests/test_phase_2_quality_gate.py"""
@pytest.mark.asyncio
async def test_get_repairs_endpoint(client, novel_and_headers):
    novel, headers = novel_and_headers
    novel_id = novel["id"]

    # Create a writing run first
    bp_resp = await client.post(
        f"/api/v1/novels/{novel_id}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    bp_id = bp_resp.json()["data"]["id"]
    await client.put(f"/api/v1/novels/{novel_id}/blueprints/{bp_id}/activate", headers=headers)
    plan_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-plans/next/generate", headers=headers)
    plan_id = plan_resp.json()["data"]["id"]
    brief_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapter-briefs/generate", headers=headers,
        json={"chapter_plan_id": plan_id})
    brief_id = brief_resp.json()["data"]["id"]
    run_resp = await client.post(
        f"/api/v1/novels/{novel_id}/writing-runs", headers=headers,
        json={"chapter_brief_id": brief_id})
    run_id = run_resp.json()["data"]["id"]

    resp = await client.get(
        f"/api/v1/novels/{novel_id}/writing-runs/{run_id}/repairs", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "repair_logs" in data
    assert "pending_repairs" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest backend/tests/test_phase_2_quality_gate.py::test_get_repairs_endpoint -x -q`
Expected: FAIL with 404

- [ ] **Step 3: Add endpoints to `backend/app/api/writing.py`**

Add to imports:
```python
from app.repositories.quality_gate_repo import RepairLogRepo, PendingRepairRepo
from app.schemas.writing import (
    # ... existing imports ...
    RepairLogOut,
    PendingRepairOut,
    ResolveRepairRequest,
)
```

Add new routes at the end of the file (before the last newline):

```python
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
    svc = _get_service(db, current_user, novel_id)
    await svc._ensure_owned_novel()
    pending_repo = PendingRepairRepo(db)
    repair = await pending_repo.get_by_id(repair_id)
    if not repair or repair.novel_id != novel_id:
        raise NotFound("修复项不存在")
    if repair.status != "pending":
        raise AppException("该修复项已处理")
    # In Phase 2, resolve marks as applied but no auto-fix of draft yet
    # Phase 4 will add actual localized rewrite here
    import datetime
    if body.action == "apply":
        await pending_repo.update_status(repair_id, "applied")
    elif body.action == "dismiss":
        await pending_repo.update_status(repair_id, "dismissed")
    else:
        raise AppException(f"不支持的动作: {body.action}")
    await db.commit()
    # Re-check if any pending repairs remain
    remaining = await pending_repo.list_pending_by_writing_run(repair.writing_run_id)
    if not remaining:
        run = await svc.get_writing_run(repair.writing_run_id)
        run.has_pending_repairs = False
        await db.commit()
    return ApiResponse.success(message="修复项已处理")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest backend/tests/test_phase_2_quality_gate.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/writing.py backend/tests/test_phase_2_quality_gate.py
git commit -m "feat: add quality gate API endpoints"
```

---

### Task 8: Frontend Types + API + Store

**Files:**
- Modify: `frontend/src/types/writing.ts`
- Modify: `frontend/src/api/writing.ts`
- Modify: `frontend/src/stores/writing.ts`

- [ ] **Step 1: Add types to `frontend/src/types/writing.ts`**

```ts
export interface RepairLog {
  id: number
  novel_id: number
  writing_run_id: number
  issue_type: string
  description: string
  location: string
  old_text: string
  new_text: string
  created_at: string
}

export interface PendingRepairOption {
  label: string
  summary: string
}

export interface PendingRepair {
  id: number
  novel_id: number
  chapter_id: number
  writing_run_id: number
  issue_type: string
  description: string
  location: string
  context: string
  options: PendingRepairOption[] | null
  intent_type: 'choice' | 'freeform'
  status: 'pending' | 'applied' | 'dismissed'
  created_at: string
}

export interface RepairsResponse {
  repair_logs: RepairLog[]
  pending_repairs: PendingRepair[]
}
```

- [ ] **Step 2: Add API functions to `frontend/src/api/writing.ts`**

```ts
import type { RepairsResponse } from '@/types/writing'

export function getRepairs(novelId: number, runId: number): Promise<RepairsResponse> {
  return client.get(`/novels/${novelId}/writing-runs/${runId}/repairs`)
}

export function getPendingRepairs(novelId: number, runId: number): Promise<{ id: number; issue_type: string }[]> {
  return client.get(`/novels/${novelId}/writing-runs/${runId}/repairs/pending`)
}

export function resolveRepair(
  novelId: number,
  repairId: number,
  payload: { action: 'apply' | 'dismiss'; choice_index?: number; intent_text?: string },
): Promise<void> {
  return client.put(`/novels/${novelId}/writing/repairs/${repairId}/resolve`, payload)
}
```

- [ ] **Step 3: Extend store in `frontend/src/stores/writing.ts`**

Add imports:
```ts
import type { RepairLog, PendingRepair, RepairsResponse } from '@/types/writing'
import * as api from '@/api/writing'
```

Add refs after existing state:
```ts
const repairLogs = ref<RepairLog[]>([])
const pendingRepairs = ref<PendingRepair[]>([])
```

Add actions:
```ts
async function fetchRepairs(novelId: number, runId: number) {
  const data = await api.getRepairs(novelId, runId)
  repairLogs.value = data.repair_logs
  pendingRepairs.value = data.pending_repairs
}

async function resolveRepair(novelId: number, repairId: number, payload: { action: string; choice_index?: number; intent_text?: string }) {
  await api.resolveRepair(novelId, repairId, payload)
  pendingRepairs.value = pendingRepairs.value.map(r =>
    r.id === repairId ? { ...r, status: 'applied' as const } : r,
  )
}
```

Return values:
```ts
return {
  blueprints, activeBlueprint, latestPlan, latestBrief, latestContext,
  writingRuns, loading, repairLogs, pendingRepairs,
  fetchBlueprints, generateBlueprint, activateBlueprint, updateBlueprint,
  generateChapterPlan, generateChapterBrief, generateContextPackage,
  createWritingRun, acceptRun, discardRun, fetchWritingRuns,
  fetchRepairs, resolveRepair,
}
```

- [ ] **Step 4: TypeScript check**

Run: `npm run type-check` in `frontend/`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/writing.ts frontend/src/api/writing.ts frontend/src/stores/writing.ts
git commit -m "feat: add frontend types, API, store for quality gate repairs"
```

---

### Task 9: Editor View — Two-Column Layout

**Files:**
- Modify: `frontend/src/views/editor/EditorView.vue`
- Modify: `frontend/src/components/writing/WritingEditor.vue`

- [ ] **Step 1: Modify `WritingEditor.vue` to support two-column layout**

Change the template structure:

```vue
<template>
  <div class="writing-editor">
    <div class="writing-editor__header">
      <!-- existing header unchanged -->
    </div>
    <div class="writing-editor__body">
      <div class="writing-editor__content" :class="{ 'with-sidebar': hasRepairs }">
        <!-- existing title and content inputs -->
      </div>
      <RepairSidebar
        v-if="hasRepairs"
        :repair-logs="repairLogs"
        :pending-repairs="pendingRepairs"
        @resolve="handleResolveRepair"
      />
    </div>
  </div>
</template>
```

Add props:
```ts
const props = withDefaults(defineProps<{
  title?: string
  content?: string
  status?: string
  saving?: boolean
  savedAt?: string
  repairLogs?: RepairLog[]
  pendingRepairs?: PendingRepair[]
}>(), {
  repairLogs: () => [],
  pendingRepairs: () => [],
})

const emit = defineEmits<{
  (e: 'resolve', repairId: number, payload: { action: string; choice_index?: number; intent_text?: string }): void
}>()

const hasRepairs = computed(() =>
  props.pendingRepairs.length > 0 || props.repairLogs.length > 0,
)
```

Update styles:
```scss
.writing-editor__body {
  display: flex;
  flex: 1;
  overflow: hidden;

  .writing-editor__content {
    flex: 1;
    max-width: 760px;
    margin: 0 auto;
    overflow-y: auto;

    &.with-sidebar {
      max-width: none;
      margin: 0;
      padding: 0 $spacing-lg;
    }
  }
}
```

Add import:
```ts
import RepairSidebar from './RepairSidebar.vue'
```

- [ ] **Step 2: TypeScript check**

Run: `npm run type-check` in `frontend/`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/writing/WritingEditor.vue
git commit -m "feat: add two-column layout support to WritingEditor"
```

---

### Task 10: RepairSidebar Component

**Files:**
- Create: `frontend/src/components/writing/RepairSidebar.vue`
- Create: `frontend/src/components/writing/RepairItem.vue`

- [ ] **Step 1: Create `frontend/src/components/writing/RepairItem.vue`**

```vue
<script setup lang="ts">
import type { RepairLog, PendingRepair } from '@/types/writing'

const props = defineProps<{
  repair: RepairLog | PendingRepair
  type: 'log' | 'pending'
}>()

const emit = defineEmits<{
  (e: 'resolve', repairId: number, payload: { action: string; choice_index?: number; intent_text?: string }): void
}>()

const isLog = computed(() => props.type === 'log')
const isPending = computed(() => props.type === 'pending')

const selectedOption = ref<number | null>(null)
const intentText = ref('')
const processing = ref(false)

const pending = computed(() => props.repair as PendingRepair)

const issueTypeLabels: Record<string, string> = {
  character_choice: '角色抉择',
  expression: '表达方式',
  direction: '创作方向',
  task_completion: '任务完成度',
  style: '风格',
  character: '人设',
  continuity: '连续性',
  world: '世界观',
  foreshadowing: '伏笔',
  length: '篇幅',
}

const issueTypeLabel = computed(() => issueTypeLabels[props.repair.issue_type] || props.repair.issue_type)

async function handleApply() {
  if (processing.value) return
  processing.value = true
  try {
    if (pending.value.intent_type === 'choice' && selectedOption.value !== null) {
      emit('resolve', pending.value.id, { action: 'apply', choice_index: selectedOption.value })
    } else if (pending.value.intent_type === 'freeform' && intentText.value.trim()) {
      emit('resolve', pending.value.id, { action: 'apply', intent_text: intentText.value.trim() })
    }
  } finally {
    processing.value = false
  }
}

async function handleDismiss() {
  if (processing.value) return
  processing.value = true
  try {
    emit('resolve', pending.value.id, { action: 'dismiss' })
  } finally {
    processing.value = false
  }
}
</script>

<template>
  <div v-if="isLog" class="repair-item repair-item--log">
    <div class="repair-item__header">
      <el-tag size="small" type="info">{{ issueTypeLabel }}</el-tag>
      <el-text size="small" type="info">{{ repair.description }}</el-text>
    </div>
  </div>

  <div v-else class="repair-item repair-item--pending">
    <div class="repair-item__header">
      <el-tag size="small" type="warning">{{ issueTypeLabel }}</el-tag>
      <el-text size="small" class="repair-item__desc">{{ pending.description }}</el-text>
    </div>

    <el-text size="small" type="info" class="repair-item__context">
      {{ pending.context.slice(0, 100) }}{{ pending.context.length > 100 ? '...' : '' }}
    </el-text>

    <div v-if="pending.intent_type === 'choice' && pending.options" class="repair-item__options">
      <el-radio-group v-model="selectedOption">
        <el-radio v-for="(opt, i) in pending.options" :key="i" :value="i" size="small">
          <div class="repair-item__option">
            <div class="repair-item__option-label">{{ opt.label }}</div>
            <div class="repair-item__option-summary">{{ opt.summary }}</div>
          </div>
        </el-radio>
      </el-radio-group>
    </div>

    <div v-else-if="pending.intent_type === 'freeform'" class="repair-item__intent">
      <el-input
        v-model="intentText"
        :rows="3"
        type="textarea"
        placeholder="描述你希望的方向..."
      />
    </div>

    <div class="repair-item__actions">
      <el-button size="small" @click="handleDismiss">忽略</el-button>
      <el-button
        size="small"
        type="primary"
        :disabled="(pending.intent_type === 'choice' && selectedOption === null) || (pending.intent_type === 'freeform' && !intentText.trim())"
        :loading="processing"
        @click="handleApply"
      >
        {{ pending.intent_type === 'choice' ? '应用选择' : '按意图修复' }}
      </el-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.repair-item {
  padding: $spacing-sm;
  border-radius: $radius-md;
}

.repair-item--log {
  background: $color-bg-secondary;
}

.repair-item--pending {
  border: 1px solid $color-border;
  background: $color-bg-card;
}

.repair-item__header {
  display: flex;
  align-items: flex-start;
  gap: $spacing-sm;
  margin-bottom: $spacing-xs;
}

.repair-item__desc {
  flex: 1;
  line-height: 1.4;
}

.repair-item__context {
  display: block;
  padding: $spacing-xs $spacing-sm;
  background: $color-bg-secondary;
  border-radius: $radius-sm;
  margin-bottom: $spacing-sm;
  font-style: italic;
}

.repair-item__options {
  margin-bottom: $spacing-sm;
}

.repair-item__option {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.repair-item__option-label {
  font-weight: 600;
  color: $color-text;
}

.repair-item__option-summary {
  font-size: 12px;
  color: $color-text-secondary;
}

.repair-item__intent {
  margin-bottom: $spacing-sm;
}

.repair-item__actions {
  display: flex;
  justify-content: flex-end;
  gap: $spacing-sm;
}
</style>
```

- [ ] **Step 2: Create `frontend/src/components/writing/RepairSidebar.vue`**

```vue
<script setup lang="ts">
import type { RepairLog, PendingRepair } from '@/types/writing'

const props = defineProps<{
  repairLogs: RepairLog[]
  pendingRepairs: PendingRepair[]
}>()

const emit = defineEmits<{
  (e: 'resolve', repairId: number, payload: { action: string; choice_index?: number; intent_text?: string }): void
}>()

const logsExpanded = ref(false)

function handleResolve(repairId: number, payload: { action: string; choice_index?: number; intent_text?: string }) {
  emit('resolve', repairId, payload)
}

const unresolvedCount = computed(() =>
  props.pendingRepairs.filter(r => r.status === 'pending').length,
)
</script>

<template>
  <aside class="repair-sidebar">
    <div class="repair-sidebar__header">
      <h3 class="repair-sidebar__title">修复</h3>
      <el-tag v-if="unresolvedCount > 0" size="small" type="warning">
        {{ unresolvedCount }} 项待处理
      </el-tag>
    </div>

    <!-- Auto Repair Logs -->
    <div v-if="repairLogs.length > 0" class="repair-sidebar__section">
      <div class="repair-sidebar__section-header" @click="logsExpanded = !logsExpanded">
        <el-text size="small" type="info">
          自动修复 ({{ repairLogs.length }})
        </el-text>
        <el-icon :class="{ expanded: logsExpanded }">
          <ArrowRight />
        </el-icon>
      </div>
      <Transition name="collapse">
        <div v-show="logsExpanded" class="repair-sidebar__logs">
          <RepairItem
            v-for="log in repairLogs"
            :key="log.id"
            :repair="log"
            type="log"
          />
        </div>
      </Transition>
    </div>

    <!-- Pending Repairs -->
    <div class="repair-sidebar__section">
      <div class="repair-sidebar__section-header">
        <el-text size="small" type="info">待处理修复</el-text>
      </div>
      <div v-if="pendingRepairs.length === 0" class="repair-sidebar__empty">
        <el-text size="small" type="info">暂无待处理项</el-text>
      </div>
      <div v-else class="repair-sidebar__items">
        <RepairItem
          v-for="repair in pendingRepairs"
          :key="repair.id"
          :repair="repair"
          type="pending"
          @resolve="handleResolve"
        />
      </div>
    </div>
  </aside>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.repair-sidebar {
  width: 320px;
  min-width: 320px;
  border-left: 1px solid $color-border;
  background: $color-bg-card;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.repair-sidebar__header {
  padding: $spacing-md;
  border-bottom: 1px solid $color-border;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.repair-sidebar__title {
  margin: 0;
  font-size: $font-size-md;
  font-weight: 600;
  color: $color-text;
}

.repair-sidebar__section {
  padding: $spacing-sm $spacing-md;
  border-bottom: 1px solid $color-border;

  &:last-child {
    border-bottom: none;
  }
}

.repair-sidebar__section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
  margin-bottom: $spacing-sm;

  .el-icon {
    transition: transform 0.2s;
    font-size: 14px;

    &.expanded {
      transform: rotate(90deg);
    }
  }
}

.repair-sidebar__logs {
  display: flex;
  flex-direction: column;
  gap: $spacing-xs;
}

.repair-sidebar__items {
  display: flex;
  flex-direction: column;
  gap: $spacing-sm;
}

.repair-sidebar__empty {
  text-align: center;
  padding: $spacing-lg 0;
}

.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.2s ease;
}
.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
```

- [ ] **Step 3: TypeScript check**

Run: `npm run type-check` in `frontend/`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/writing/RepairSidebar.vue frontend/src/components/writing/RepairItem.vue
git commit -m "feat: add RepairSidebar and RepairItem components"
```

---

### 未纳入范围

- **区域锁定（region locking）** — 前端用 `el-input` textarea 无法对正文做局部只读/灰底标记，需要替换为 contenteditable 或集成富文本编辑器。当前替代方案是侧栏标记位置，用户通过在侧栏操作而不是直接编辑来避免冲突。后续 Phase 4 配合 DraftVersion 时一并替换编辑器实现。
- **局部改写 AI Agent** — `PendingRepair` resolve 接口目前只是状态标记（`applied`），实际调用 AI 按用户意图局部替换正文需要一个新的 `LocalRewriteAgent`，属于 Phase 4 辅助修改阶段的范围。

### Task 11: End-to-End Integration

**Files:**
- Modify: `frontend/src/views/editor/EditorView.vue`
- Write: `frontend/src/components/writing/WritingEditor.vue` — final integration (connect store + sidebar)

- [ ] **Step 1: Modify `EditorView.vue` to load repair data and pass to WritingEditor**

```vue
<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { useWritingStore } from '@/stores/writing'
import { ElMessage } from 'element-plus'
import WritingEditor from '@/components/writing/WritingEditor.vue'

const route = useRoute()
const novelStore = useNovelStore()
const writingStore = useWritingStore()

const novelId = Number(route.params.id)
const chapterId = Number(route.params.chapterId)
const novel = computed(() => novelStore.currentNovel)
const chapter = computed(() => novelStore.currentChapter)

onMounted(async () => {
  await novelStore.fetchNovelDetail(novelId)
  if (chapterId) {
    await novelStore.fetchChapter(chapterId)
  }
  // Load repairs if we have a writing run context
  const lastRun = writingStore.writingRuns[0]
  if (lastRun && lastRun.status === 'completed') {
    await writingStore.fetchRepairs(novelId, lastRun.id)
  }
})

function handleResolveRepair(repairId: number, payload: { action: string; choice_index?: number; intent_text?: string }) {
  writingStore.resolveRepair(novelId, repairId, payload)
}
</script>

<template>
  <WritingEditor
    v-if="novel && chapter"
    :title="chapter.title"
    :content="chapter.content"
    :status="chapter.status"
    :saving="novelStore.saving"
    :saved-at="novelStore.savedAt"
    :repair-logs="writingStore.repairLogs"
    :pending-repairs="writingStore.pendingRepairs"
    :novel-id="novelId"
    :chapter-id="chapterId"
    @save="novelStore.saveChapter"
    @resolve="handleResolveRepair"
  />
</template>
```

- [ ] **Step 2: Update WritingEditor props to accept repairs and handle resolve**

Add to `WritingEditor.vue`:
```ts
const props = withDefaults(defineProps<{
  title?: string
  content?: string
  status?: string
  saving?: boolean
  savedAt?: string
  novelId?: number
  chapterId?: number
  repairLogs?: RepairLog[]
  pendingRepairs?: PendingRepair[]
}>(), {
  repairLogs: () => [],
  pendingRepairs: () => [],
})

const emit = defineEmits<{
  (e: 'save', chapterId: number, title: string, content: string): void
  (e: 'resolve', repairId: number, payload: { action: string; choice_index?: number; intent_text?: string }): void
}>()

function handleResolveRepair(repairId: number, payload: { action: string; choice_index?: number; intent_text?: string }) {
  emit('resolve', repairId, payload)
}
```

- [ ] **Step 3: TypeScript check + lint**

Run: `npm run type-check && npm run lint` in `frontend/`
Expected: PASS

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python -m pytest backend/tests/ -x -q`
Expected: All PASS

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete v2 Phase 2 quality gate integration"
```
