# Novel Agent v2 Phase 4 Assisted Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现“生成 → 检查 → 局部修改 → 作者确认 → 记忆提取”的单章闭环，并确保 AI 自动优化、局部修复、手动编辑和恢复都只属于当前作者可见版本，只有作者显式创建新版本时版本号才递增。

**Architecture:** 在现有 `WritingRun` 工作副本之上新增作者可见的 `DraftVersion` 聚合，由 `DraftVersionService` 统一维护当前正文、修订序号、候选应用和接受边界；扩展现有 `DraftRevision` 表达所有版本内操作；以新的 `ModificationService` 和结构化修改 Agent 生成选项及候选，但不直接覆盖正文。现有 Phase 3 规划修订、Phase 2 `PendingRepair` 和写作接受流程都委托这一聚合，前端则严格分离“当前版本”“内部修改”“版本历史”三个概念。

**Tech Stack:** Python 3.12、FastAPI、异步 SQLAlchemy、Pydantic v2、Alembic、DeepSeek/LangChain 1.x、SQLite/MySQL、pytest、Vue 3、TypeScript、Pinia、Element Plus、Vitest。

## Global Constraints

- `DraftVersion` 是作者主动发起的完整创作轮次；`DraftRevision` 是该轮次内部的一次操作记录或待确认候选。
- 初稿生成、字数补足、质量门禁最多三次检查、自动重写和自动局部替换全部在 v1 创建前收敛，不得产生 v2/v3。
- WritingRun 首次拥有可供作者处理的正文时只创建 v1；版本号只由 `POST /writing-runs/{run_id}/draft-versions` 递增。
- 同一个 WritingRun 同时最多有一个 `status == "draft"` 的 DraftVersion；数据库使用 `(writing_run_id, version)` 唯一约束，单一当前版本由服务事务保证。
- `WritingRun.draft_content` 和 `word_count` 继续作为兼容工作副本，但每次 Phase 4 写入都必须与当前 DraftVersion 在同一事务内同步。
- 修改 Agent 只能生成方向或 `candidate`，不能直接修改 DraftVersion、WritingRun、Chapter 或 ReviewIssue 状态。
- `DraftRevision.base_revision_sequence` 与 `base_content_hash` 必须同时匹配当前版本；任一不匹配即为过期候选。
- 一个候选应用后，同一 `draft_version_id + base_revision_sequence + base_content_hash` 的其他候选全部变为 `superseded`。
- `DraftRevision.sequence` 只给已经生效的内部修改编号；候选、拒绝和被替代记录保持 `sequence=0`，应用时才获得 `current.revision_sequence + 1`。因此拒绝候选不会消耗作者看到的 R1/R2 编号。
- `expanded_scope == true` 的候选必须收到显式 `confirm_expanded_scope=true` 才能应用。
- 接受 WritingRun 前必须处理当前版本的全部候选；开放的 `blocking` ReviewIssue 默认阻止接受，强制接受必须提供并保存原因。
- WritingRun 一旦 `accepted` 或 `discarded`，不得继续创建版本、恢复、手动编辑或应用候选。
- `Chapter.status == "locked"` 后，创建版本、恢复、手动编辑、应用候选和覆盖章节正文全部拒绝。
- 接受成功后当前 DraftVersion 变为 `accepted`，回填 `chapter_id`，再触发现有 PendingMemory 提取；同一个 WritingRun 不再进入 Phase 4。
- 所有跨用户或跨小说资源访问继续返回 404，避免泄露资源存在性。
- 所有结构化 AI 输出都经 Pydantic 和 patch 重建校验；AI、校验或数据库失败不能留下半成品。
- 后端默认测试命令必须离线；真实 DeepSeek 用 `integration` 标记和独立命令运行。
- 开发环境 `create_all` 与 Alembic 都必须识别新增模型，迁移 head 必须从 `e2f3a4b5c6d7` 延续。
- Vue API、vue-router、Element Plus 组件及消息 API 继续使用项目自动导入，不新增手动导入。

执行目录约定：所有 `.venv/bin/python`、Alembic 和 pytest 命令在 `backend/` 运行；所有 `npm` 命令在 `frontend/` 运行；所有 `git` 命令在仓库根目录运行。命令块之间不依赖前一个命令改变工作目录。

## File Map

### Backend additions

- `backend/app/models/draft_version.py`：DraftVersion ORM。
- `backend/app/schemas/revision.py`：版本、修订、问题和接受请求响应协议。
- `backend/app/repositories/draft_version_repo.py`：DraftVersion 与版本内 DraftRevision 查询。
- `backend/app/services/draft_version_service.py`：版本聚合、并发校验、应用/拒绝/恢复/手动保存。
- `backend/app/services/modification_service.py`：ReviewIssue 方向和候选生成。
- `backend/app/ai/modification.py`：修改 Agent 结构化协议、Fake 与 DeepSeek 实现。
- `backend/app/api/revisions.py`：Phase 4 嵌套路由。
- `backend/alembic/versions/f3a4b5c6d7e8_phase_4_assisted_revision.py`：模型扩展与数据回填。
- `backend/tests/test_phase_4_models_and_migration.py`：模型、Schema、迁移。
- `backend/tests/test_phase_4_draft_versions.py`：版本领域服务。
- `backend/tests/test_phase_4_modification.py`：选项、patch、候选和统一应用。
- `backend/tests/test_phase_4_api.py`：权限与 HTTP 契约。
- `backend/tests/test_phase_4_acceptance.py`：完整闭环。
- `backend/tests/test_phase_4_ai_integration.py`：真实修改 Agent 独立验证。

### Backend modifications

- `backend/app/models/__init__.py`
- `backend/app/models/plot_planning.py`
- `backend/app/models/quality_gate.py`
- `backend/app/models/writing.py`
- `backend/app/schemas/plot_planning.py`
- `backend/app/schemas/writing.py`
- `backend/app/repositories/plot_planning_repo.py`
- `backend/app/repositories/quality_gate_repo.py`
- `backend/app/services/writing_service.py`
- `backend/app/services/quality_gate_service.py`
- `backend/app/services/plot_planning_service.py`
- `backend/app/services/repair_service.py`
- `backend/app/ai/quality_gate.py`
- `backend/app/ai/quality_agents.py`
- `backend/app/api/writing.py`
- `backend/app/api/planning.py`
- `backend/app/main.py`
- `backend/tests/conftest.py`
- Phase 1–3 受影响测试文件。

### Frontend additions

- `frontend/src/types/revision.ts`
- `frontend/src/api/revisions.ts`
- `frontend/src/stores/revisions.ts`
- `frontend/src/components/writing/ReviewIssuePanel.vue`
- `frontend/src/components/writing/RevisionCandidatePanel.vue`
- `frontend/src/components/writing/DraftVersionTimeline.vue`
- `frontend/src/components/writing/RevisionHistoryPanel.vue`
- `frontend/src/__tests__/WritingWorkspacePhase4.spec.ts`

### Frontend modifications

- `frontend/src/types/writing.ts`
- `frontend/src/types/plotPlanning.ts`
- `frontend/src/api/writing.ts`
- `frontend/src/api/planning.ts`
- `frontend/src/stores/writing.ts`
- `frontend/src/stores/plotPlanning.ts`
- `frontend/src/components/writing/DraftRevisionDiff.vue`
- `frontend/src/views/novels/WritingWorkspaceView.vue`

---

### Task 1: Pin Python 3.12 and make the default test suite offline

**Files:**

- Create: `backend/.python-version`
- Modify: `backend/pytest.ini`
- Modify: `backend/tests/test_phase_1_writing_integration.py`
- Modify: `backend/tests/test_phase_2_ai_extract.py`
- Modify: `backend/tests/test_phase_3_dynamic_plot_planning_integration.py`
- Create: `backend/tests/test_engineering_baseline.py`

**Interfaces:**

- `pytest.mark.integration` denotes tests that may access DeepSeek or other external services.
- Default command excludes integration tests through `addopts = -m "not integration"`.
- Explicit live command clears default addopts: `.venv/bin/python -m pytest -o addopts='' -m integration ...`.
- `.python-version` contains exactly `3.12`.

- [ ] **Step 1: Verify and correct the local Python runtime before changing code**

Run from `backend/`:

```sh
.venv/bin/python --version
python3.12 --version
```

Expected before correction: the existing virtualenv reports 3.11 while `python3.12` is available. Rebuild the environment without deleting project data:

```sh
python3.12 -m venv --clear .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python --version
```

Expected after correction: `Python 3.12.x`.

- [ ] **Step 2: Add the failing runtime and marker test**

Create `backend/tests/test_engineering_baseline.py`:

```python
import sys

import pytest


def test_backend_runtime_is_python_312():
    assert sys.version_info[:2] == (3, 12)


def test_integration_marker_is_registered(pytestconfig):
    markers = pytestconfig.getini("markers")
    assert any(line.startswith("integration:") for line in markers)
```

Run:

```sh
.venv/bin/python -m pytest tests/test_engineering_baseline.py -x -q
```

Expected RED: marker registration assertion fails.

- [ ] **Step 3: Pin the version and exclude live tests by default**

Write `backend/.python-version` as:

```text
3.12
```

Update `backend/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
pythonpath = .
testpaths = tests
addopts = -m "not integration"
markers =
    integration: calls a real external AI service and is excluded from the default suite
```

In each live test module, preserve the existing `skipif` and combine it with the marker:

```python
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not settings.DEEPSEEK_API_KEY,
        reason="DEEPSEEK_API_KEY not set — set in .env to run AI integration tests",
    ),
]
```

The Phase 3 integration module uses `os.environ`; keep that source but add the same `integration` marker.

- [ ] **Step 4: Prove the default suite does not collect live tests**

Run:

```sh
.venv/bin/python -m pytest --collect-only -q
```

Expected: the three live modules are deselected and no collected node comes from files ending in `_integration.py` that call real DeepSeek.

Run:

```sh
.venv/bin/python -m pytest tests/test_engineering_baseline.py -x -q
```

Expected GREEN: 2 passed.

- [ ] **Step 5: Commit the engineering baseline**

```sh
git add backend/.python-version backend/pytest.ini backend/tests/test_engineering_baseline.py backend/tests/test_phase_1_writing_integration.py backend/tests/test_phase_2_ai_extract.py backend/tests/test_phase_3_dynamic_plot_planning_integration.py
git commit -m "test: isolate live AI integration suite"
```

---

### Task 2: Add DraftVersion and extend revision/review persistence

**Files:**

- Create: `backend/app/models/draft_version.py`
- Modify: `backend/app/models/plot_planning.py`
- Modify: `backend/app/models/quality_gate.py`
- Modify: `backend/app/models/writing.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/f3a4b5c6d7e8_phase_4_assisted_revision.py`
- Create: `backend/tests/test_phase_4_models_and_migration.py`

**Interfaces:**

- `DraftVersion.status`: `draft | accepted | rejected | archived`.
- `DraftRevision.source_type`: `planning_decision | review_issue | author_request | manual_edit | restore`.
- `DraftRevision.status`: `candidate | applied | rejected | superseded`.
- `ReviewIssue.severity`: `blocking | major | minor`.
- `ReviewIssue.resolution_mode`: `auto_fixable | needs_intent`.
- Phase 4-created DraftRevision always has `draft_version_id`; migrated orphan legacy rows may remain null only at the database compatibility layer.

- [ ] **Step 1: Write failing ORM boundary tests**

Add tests that create one WritingRun and assert the exact persistence boundary:

```python
@pytest.mark.asyncio
async def test_draft_version_and_revision_are_separate_layers(db):
    run = await make_writing_run(db, draft_content="初稿正文", status="completed")
    version = DraftVersion(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        version=1,
        title="首次生成",
        content="初稿正文",
        word_count=4,
        change_reason="首次生成",
        status="draft",
        revision_sequence=0,
    )
    db.add(version)
    await db.flush()
    revision = DraftRevision(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        draft_version_id=version.id,
        sequence=1,
        source_type="manual_edit",
        source_id=None,
        base_revision_sequence=0,
        base_content_hash=hash_content("初稿正文"),
        base_content="初稿正文",
        candidate_content="补充后的正文",
        patches_json=[],
        diff_json={"old": "初稿正文", "new": "补充后的正文"},
        scope_json={"type": "manual"},
        reason="补充角色动机",
        expanded_scope=False,
        status="applied",
    )
    db.add(revision)
    await db.flush()
    assert version.version == 1
    assert revision.draft_version_id == version.id
    assert revision.source_type == "manual_edit"
```

Also assert `PendingRepair.review_issue_id`, `ReviewIssue.resolution_mode`, `repair_options_json`, `resolved_by_revision_id`, `ignored_reason`, and `DraftVersion.acceptance_override_reason` persist correctly.

- [ ] **Step 2: Run the focused test and confirm RED**

```sh
.venv/bin/python -m pytest tests/test_phase_4_models_and_migration.py -x -q
```

Expected RED: `DraftVersion` and new columns do not exist.

- [ ] **Step 3: Implement the ORM fields and constraints**

Create `DraftVersion` with these exact fields:

```python
class DraftVersion(Base):
    __tablename__ = "draft_versions"
    __table_args__ = (
        UniqueConstraint("writing_run_id", "version", name="uq_draft_versions_run_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    writing_run_id: Mapped[int] = mapped_column(ForeignKey("writing_runs.id"), nullable=False, index=True)
    based_on_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("draft_versions.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(nullable=False, default="draft")
    revision_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acceptance_override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
```

Extend `DraftRevision` with `draft_version_id`, `sequence`（默认 0）, `source_type`, `source_id`, `base_revision_sequence`, `base_content_hash`, `patches_json`, `expanded_scope`, and `expanded_scope_reason`. Do not add a uniqueness constraint on sequence because multiple unapplied candidates intentionally use 0. Keep `parent_revision_id` and `decision_id`.

Extend `ReviewIssue` with `chapter_id`, `resolution_mode`, `repair_options_json`, `resolved_by_revision_id`, and `ignored_reason`. Keep `acceptance_blocking` during compatibility migration.

Extend `PendingRepair` with nullable `review_issue_id` so the old repair endpoint can delegate to the canonical ReviewIssue.

Export `DraftVersion` from `app.models.__init__` so startup `Base.metadata.create_all` includes the table.

- [ ] **Step 4: Write a portable Alembic migration and backfill existing runs**

The migration must use `revision = "f3a4b5c6d7e8"` and `down_revision = "e2f3a4b5c6d7"`. In `upgrade()`:

1. Create `draft_versions` and its indexes/unique constraint.
2. Add the DraftRevision, ReviewIssue, and PendingRepair columns with temporary server defaults where required.
3. Select every WritingRun with non-empty `draft_content` and insert exactly one v1:
   - `accepted → accepted`
   - `discarded → rejected`
   - all other statuses → `draft`
4. Backfill each existing DraftRevision by `writing_run_id`:
   - assign its run's v1 id;
   - assign a monotonically increasing `sequence` ordered by id only to legacy `status=applied` rows; candidate/superseded rows receive 0;
   - `source_type = planning_decision` when `decision_id` exists, otherwise `author_request`;
   - `source_id = decision_id` when present;
   - `base_revision_sequence = 0`;
   - `base_content_hash = sha256(base_content.encode("utf-8")).hexdigest()`;
   - `patches_json = []`, `expanded_scope = false`.
5. Normalize ReviewIssue rows:
   - old `needs_intent` becomes `resolution_mode=needs_intent`;
   - old `auto_fixable` becomes `resolution_mode=auto_fixable`;
   - any other old value becomes `resolution_mode=needs_intent`;
   - `acceptance_blocking=true` becomes `severity=blocking`;
   - non-blocking old `warning` becomes `severity=minor`;
   - every other non-blocking row becomes `severity=major`.
6. Remove temporary server defaults but retain nullable `draft_version_id` only for legacy rows without a WritingRun.

`downgrade()` drops added columns before dropping `draft_versions`, restores legacy severity from `resolution_mode`, and leaves legacy DraftRevision base/diff data intact.

`test_phase_4_models_and_migration.py` 还要使用 `tmp_path` 和 `subprocess.run()` 执行真实往返：子进程环境设置临时 `DATABASE_URL`，先升级到 `e2f3a4b5c6d7`，使用标准库 `sqlite3` 插入 WritingRun、ReviewIssue 和 DraftRevision 旧数据，再升级到 head 并断言 v1/字段回填，最后降级到 `e2f3a4b5c6d7` 后再次升级。该测试不复用 `conftest.py` 的应用数据库。

- [ ] **Step 5: Verify models and migration on a disposable database**

```sh
.venv/bin/python -m pytest tests/test_phase_4_models_and_migration.py -x -q
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic current
```

Expected GREEN: model tests pass and current revision is `f3a4b5c6d7e8`.

- [ ] **Step 6: Commit persistence**

```sh
git add backend/app/models backend/alembic/versions/f3a4b5c6d7e8_phase_4_assisted_revision.py backend/tests/test_phase_4_models_and_migration.py
git commit -m "feat: add phase 4 draft version persistence"
```

---

### Task 3: Add typed schemas and version repositories

**Files:**

- Create: `backend/app/schemas/revision.py`
- Modify: `backend/app/schemas/plot_planning.py`
- Modify: `backend/app/schemas/writing.py`
- Create: `backend/app/repositories/draft_version_repo.py`
- Modify: `backend/app/repositories/quality_gate_repo.py`
- Modify: `backend/app/repositories/plot_planning_repo.py`
- Modify: `backend/tests/test_phase_4_models_and_migration.py`

**Interfaces:**

```python
DraftVersionRepo.get(version_id, novel_id)
DraftVersionRepo.get_current(writing_run_id)
DraftVersionRepo.list_by_run(writing_run_id)
DraftVersionRepo.next_version_number(writing_run_id)
DraftVersionRepo.create(novel_id, data)
DraftVersionRepo.update(version, data)
DraftVersionRepo.list_revisions(draft_version_id)
DraftVersionRepo.get_revision(revision_id, novel_id)
DraftVersionRepo.create_revision(novel_id, data)
DraftVersionRepo.list_sibling_candidates(draft_version_id, base_revision_sequence, base_content_hash)
```

- [ ] **Step 1: Add failing schema and query tests**

Test all request validators and ordering:

```python
def test_revision_requests_enforce_author_intent_and_concurrency():
    assert CreateDraftVersionRequest(
        based_on_version_id=4,
        change_reason="调整节奏",
    ).based_on_version_id == 4
    with pytest.raises(ValidationError):
        CreateDraftVersionRequest(based_on_version_id=4, change_reason="")
    with pytest.raises(ValidationError):
        CreateRevisionRequest()
    with pytest.raises(ValidationError):
        CreateRevisionRequest(option_index=0, custom_intent="更克制")
    assert ManualRevisionRequest(
        content="新正文",
        change_reason="补充动机",
        base_revision_sequence=2,
    ).base_revision_sequence == 2
```

Repository test expectations:

```python
versions = await repo.list_by_run(run.id)
assert [item.version for item in versions] == [2, 1]
assert (await repo.get_current(run.id)).version == 2
assert await repo.next_version_number(run.id) == 3
assert await repo.list_revisions(current.id) == []
```

- [ ] **Step 2: Run and confirm RED**

```sh
.venv/bin/python -m pytest tests/test_phase_4_models_and_migration.py -x -q
```

Expected RED: schema and repository imports fail.

- [ ] **Step 3: Implement the exact Pydantic contracts**

`backend/app/schemas/revision.py` defines:

```python
DraftVersionStatus = Literal["draft", "accepted", "rejected", "archived"]
DraftRevisionStatus = Literal["candidate", "applied", "rejected", "superseded"]
DraftRevisionSource = Literal[
    "planning_decision", "review_issue", "author_request", "manual_edit", "restore"
]
IssueSeverity = Literal["blocking", "major", "minor"]
IssueResolutionMode = Literal["auto_fixable", "needs_intent"]
```

Add response models `DraftVersionOut`, `DraftRevisionOut`, `ReviewIssueOut`, `RepairOptionOut` and request models:

```python
class CreateDraftVersionRequest(BaseModel):
    based_on_version_id: int
    change_reason: str = Field(min_length=1, max_length=500)


class RestoreVersionRequest(BaseModel):
    base_revision_sequence: int = Field(ge=0)
    change_reason: str = Field(default="恢复历史版本", min_length=1, max_length=500)


class ManualRevisionRequest(BaseModel):
    content: str
    change_reason: str = Field(min_length=1, max_length=500)
    base_revision_sequence: int = Field(ge=0)


class CreateRevisionRequest(BaseModel):
    option_index: int | None = Field(default=None, ge=0)
    custom_intent: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_exactly_one_direction(self):
        if (self.option_index is None) == (self.custom_intent is None):
            raise ValueError("必须且只能提供 option_index 或 custom_intent")
        return self


class IgnoreIssueRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ApplyRevisionRequest(BaseModel):
    confirm_expanded_scope: bool = False


class AcceptWritingRunRequest(BaseModel):
    force_accept: bool = False
    force_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_force_reason(self):
        if self.force_accept and not self.force_reason:
            raise ValueError("强制接受必须填写原因")
        if not self.force_accept and self.force_reason:
            raise ValueError("未强制接受时不能填写强制原因")
        return self
```

Move the public `DraftRevisionOut` import to this module and re-export it from `schemas.plot_planning` during compatibility. Extend `PendingRepairOut` with `review_issue_id`.

- [ ] **Step 4: Implement repository operations with ownership filters**

All get/list methods include `novel_id` or operate only after a service-owned WritingRun has been checked. Ordering is deterministic:

- versions: `version DESC`;
- revisions: `created_at DESC, id DESC`; the UI filters `status=applied` and uses positive sequence for R1/R2 display;
- current: `status == "draft"` and `scalar_one_or_none()` so corrupt double-current data fails loudly;
- sibling candidates: exact version, base sequence, hash, and `status == "candidate"`.

Extend `ReviewIssueRepo` with:

```python
get(issue_id, novel_id)
list_by_writing_run(writing_run_id, status=None)
list_open_blocking(writing_run_id)
update(issue, data)
```

Extend `PendingRepairRepo` with `get_by_review_issue(review_issue_id)` and allow `chapter_id: Optional[int]`. Keep PlotPlanningRepo methods as compatibility delegators until Task 7.

- [ ] **Step 5: Run focused tests and commit**

```sh
.venv/bin/python -m pytest tests/test_phase_4_models_and_migration.py -x -q
git add backend/app/schemas backend/app/repositories backend/tests/test_phase_4_models_and_migration.py
git commit -m "feat: add phase 4 schemas and repositories"
```

---

### Task 4: Implement DraftVersionService lifecycle without AI

**Files:**

- Create: `backend/app/services/draft_version_service.py`
- Create: `backend/tests/test_phase_4_draft_versions.py`

**Interfaces:**

```python
DraftVersionService(db, user_id, novel_id)
DraftVersionService.ensure_initial_version(run, title="首次生成") -> DraftVersion
DraftVersionService.list_versions(run_id) -> list[DraftVersion]
DraftVersionService.get_version(version_id) -> DraftVersion
DraftVersionService.create_new_version(run_id, based_on_version_id, change_reason) -> DraftVersion
DraftVersionService.save_manual_revision(run_id, content, change_reason, base_revision_sequence) -> tuple[DraftVersion, DraftRevision]
DraftVersionService.restore_into_current(source_version_id, base_revision_sequence, change_reason) -> tuple[DraftVersion, DraftRevision]
DraftVersionService.reject_revision(revision_id) -> DraftRevision
DraftVersionService.mark_run_rejected(run) -> DraftVersion | None
```

- [ ] **Step 1: Write lifecycle tests that encode the approved version semantics**

Tests must cover:

```python
v1 = await service.ensure_initial_version(run)
same_v1 = await service.ensure_initial_version(run)
assert same_v1.id == v1.id
assert [v.version for v in await service.list_versions(run.id)] == [1]

v1_after_manual, r1 = await service.save_manual_revision(
    run.id,
    content="初稿正文，补充角色动机。",
    change_reason="补充角色动机",
    base_revision_sequence=0,
)
assert v1_after_manual.version == 1
assert v1_after_manual.revision_sequence == 1
assert r1.source_type == "manual_edit"
assert r1.status == "applied"

v2 = await service.create_new_version(run.id, v1.id, "重新调整节奏")
assert v2.version == 2
assert v2.status == "draft"
assert (await service.get_version(v1.id)).status == "archived"
```

Add negative cases for stale `base_revision_sequence`, accepted/discarded runs, current `locked` target chapter, source version from another run/novel, and a second current draft.

- [ ] **Step 2: Run and confirm RED**

```sh
.venv/bin/python -m pytest tests/test_phase_4_draft_versions.py -x -q
```

Expected RED: `DraftVersionService` is missing.

- [ ] **Step 3: Implement ownership and mutability guards**

Private helpers have these responsibilities:

```python
async def _get_owned_run(self, run_id: int) -> WritingRun
async def _get_current_mutable_version(self, run: WritingRun) -> DraftVersion
async def _ensure_target_unlocked(self, run: WritingRun) -> None
def _count_words(self, content: str) -> int
def _hash_content(self, content: str) -> str
def _single_patch(self, base: str, candidate: str, reason: str) -> list[dict]
```

`_single_patch` computes the longest common prefix and suffix, then stores one exact patch for the changed middle. It returns `[]` only when content is identical; identical manual saves are rejected as `BadRequest("正文没有变化")`.

- [ ] **Step 4: Implement idempotent v1 and explicit vN+1**

`ensure_initial_version()`:

- requires non-empty `run.draft_content`;
- returns an existing version without mutation;
- otherwise creates v1 with the run's current final content;
- does not create a DraftRevision for generation-internal rewrites.

`create_new_version()` executes in one nested transaction:

1. Verify run is neither accepted nor discarded.
2. Verify target chapter is not locked.
3. Verify source version belongs to this run and novel.
4. Verify exactly one current draft exists.
5. Archive that current draft.
6. Create `max(version)+1` with source content and `revision_sequence=0`.
7. Synchronize WritingRun content and word count.

Retry is not automatic on unique constraint failure; return a business conflict asking the client to refresh.

- [ ] **Step 5: Implement applied manual and restore revisions**

Both operations check `base_revision_sequence`, construct exact patches and diff, set the applied DraftRevision `sequence` and DraftVersion `revision_sequence` to the same next value, and synchronize the run in one commit.

Restore uses `source_type="restore"`, `source_id=source_version_id`, and never creates another DraftVersion. Manual edit uses `source_type="manual_edit"`, `source_id=None`.

- [ ] **Step 6: Run focused tests and commit**

```sh
.venv/bin/python -m pytest tests/test_phase_4_draft_versions.py -x -q
git add backend/app/services/draft_version_service.py backend/tests/test_phase_4_draft_versions.py
git commit -m "feat: implement draft version lifecycle"
```

---

### Task 5: Create v1 after internal generation converges and accept from the current version

**Files:**

- Modify: `backend/app/services/writing_service.py`
- Modify: `backend/app/schemas/writing.py`
- Modify: `backend/app/api/writing.py`
- Modify: `backend/tests/test_phase_1_writing.py`
- Modify: `backend/tests/test_phase_2_quality_gate.py`
- Modify: `backend/tests/test_phase_3_dynamic_plot_planning.py`
- Modify: `backend/tests/test_phase_4_draft_versions.py`

**Interfaces:**

```python
WritingService.accept_writing_run(
    run_id: int,
    force_accept: bool = False,
    force_reason: str | None = None,
) -> tuple[Chapter, dict]
```

- [ ] **Step 1: Add failing tests for one v1 after multiple internal rewrites**

Use a counting fake generator and gate agent that forces two rewrites, then passes:

```python
run = await service.create_writing_run(brief.id)
versions = await DraftVersionRepo(db).list_by_run(run.id)
assert generator.generate_calls == 3
assert len(versions) == 1
assert versions[0].version == 1
assert versions[0].content == run.draft_content
assert versions[0].revision_sequence == 0
```

Add the Phase 3 `decision_required` case: a partial non-empty draft creates v1, resolving and applying the planning candidate changes v1 content but not its version number.

- [ ] **Step 2: Add failing acceptance boundary tests**

Verify:

- an open candidate blocks accept even with `force_accept=true`;
- an open blocking issue blocks normal accept;
- `force_accept=true` without a reason fails schema validation;
- force accept with a reason stores `DraftVersion.acceptance_override_reason`;
- accept writes current DraftVersion content, not a stale manually assigned WritingRun value;
- accepted version becomes frozen and receives `chapter_id`;
- discard marks the current version `rejected`;
- accepted and discarded runs reject further Phase 4 writes.

- [ ] **Step 3: Run focused tests and confirm RED**

```sh
.venv/bin/python -m pytest tests/test_phase_4_draft_versions.py tests/test_phase_2_quality_gate.py -x -q
```

- [ ] **Step 4: Integrate v1 creation at the correct boundary**

After generation, expansion, and quality-gate retry loops have finished, call:

```python
if run.status in ("completed", "decision_required") and run.draft_content:
    await DraftVersionService(
        self.db,
        self.user_id,
        self.novel_id,
    ).ensure_initial_version(run)
```

Place this once after the Phase 1/2 and Phase 3 branches, before the final commit. Do not call it inside a retry loop. In the Phase 3 `decision_required` branch, update the run first and then create v1 before any candidate references it.

- [ ] **Step 5: Read the current version during acceptance**

Acceptance performs, in order:

1. Existing ownership/run status/planning checks.
2. Fetch exactly one current draft version.
3. Reject any current-version DraftRevision in `candidate` status.
4. Query open blocking ReviewIssues.
5. If blocking issues exist, require `force_accept` and non-empty `force_reason`.
6. Copy DraftVersion content to Chapter.
7. Mark run accepted and version accepted; set version `chapter_id` and override reason.
8. Commit.
9. Run existing extraction service after the database commit.

Update `PUT /writing-runs/{run_id}/accept` to accept an optional `AcceptWritingRunRequest`; an omitted body behaves as `{force_accept: false}` for backward compatibility.

- [ ] **Step 6: Run Phase 1–4 focused regression and commit**

```sh
.venv/bin/python -m pytest tests/test_phase_1_writing.py tests/test_phase_2_quality_gate.py tests/test_phase_3_dynamic_plot_planning.py tests/test_phase_4_draft_versions.py -x -q
git add backend/app/services/writing_service.py backend/app/api/writing.py backend/app/schemas/writing.py backend/tests
git commit -m "feat: bind writing runs to author-visible draft versions"
```

---

### Task 6: Implement the structured Modification Agent and candidate generation

**Files:**

- Create: `backend/app/ai/modification.py`
- Create: `backend/app/services/modification_service.py`
- Create: `backend/tests/test_phase_4_modification.py`
- Create: `backend/tests/test_phase_4_ai_integration.py`

**Interfaces:**

```python
BaseModificationAgent.generate_options(context: dict) -> RepairOptionsOutput
BaseModificationAgent.create_revision(context: dict) -> ModificationOutput
ModificationService.generate_options(issue_id: int) -> list[RepairOption]
ModificationService.create_revision(
    issue_id: int,
    option_index: int | None = None,
    custom_intent: str | None = None,
) -> DraftRevision
ModificationService.ignore_issue(issue_id: int, reason: str) -> ReviewIssue
```

- [ ] **Step 1: Write Pydantic protocol tests**

Define and test these exact output models:

```python
class RepairOption(BaseModel):
    label: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    action: str = Field(min_length=1)
    expected_effect: str = Field(min_length=1)
    estimated_scope: dict
    recommended: bool = False
    recommendation_reason: str = ""


class RepairOptionsOutput(BaseModel):
    options: list[RepairOption] = Field(min_length=1, max_length=3)
    single_option_reason: str | None = None


class RevisionPatch(BaseModel):
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    original_text: str
    replacement_text: str
    reason: str = Field(min_length=1)


class ModificationOutput(BaseModel):
    candidate_content: str
    patches: list[RevisionPatch] = Field(min_length=1)
    diff: dict
    change_reason: str = Field(min_length=1)
    scope: dict
    expanded_scope: bool = False
    expanded_scope_reason: str | None = None
```

Validators reject duplicate option actions, multiple recommended options, one option without `single_option_reason`, inverted/overlapping patch offsets, and `expanded_scope=true` without a reason.

- [ ] **Step 2: Write failing service tests for non-mutating candidate generation**

The core assertion is:

```python
before = current.content
revision = await service.create_revision(issue.id, option_index=0)
await db.refresh(current)
await db.refresh(run)
await db.refresh(issue)
assert revision.status == "candidate"
assert current.content == before
assert run.draft_content == before
assert issue.status == "open"
```

Also test 1–3 options, invalid option index, custom intent, closed issue, AI exception, invalid JSON-equivalent Pydantic output, overlapping patches, mismatched `original_text`, and candidate content that differs from patch reconstruction. In every failure case assert no DraftRevision row was added.

- [ ] **Step 3: Run and confirm RED**

```sh
.venv/bin/python -m pytest tests/test_phase_4_modification.py -x -q
```

- [ ] **Step 4: Implement Fake and DeepSeek agents**

`FakeModificationAgent` accepts configured `RepairOptionsOutput`, `ModificationOutput`, or configured exceptions so service tests are deterministic.

`DeepSeekModificationAgent` 通过组合精确复用现有结构化调用：构造函数保存 `self._writer = DeepSeekWritingGenerator(api_key)`，`generate_options()` 调用 `self._writer._call_validated_json(prompt, RepairOptionsOutput)`，`create_revision()` 调用 `self._writer._call_validated_json(prompt, ModificationOutput)`；其公开边界仍然只有 `BaseModificationAgent`。Prompts include:

- full current version content;
- ReviewIssue type, severity, location, description, related memory and suggestion;
- chapter brief and WritingRun context snapshot;
- author foundation, current plot plan and locked published facts when present;
- an explicit instruction that unrelated text must be byte-for-byte unchanged;
- exact offset and patch output fields;
- permission to return one option only with a reason;
- an explicit expanded-scope explanation requirement.

The live test module has both `pytest.mark.integration` and key-based skip, and verifies real output parses, has 1–3 distinct options, and reconstructs the returned candidate from patches.

- [ ] **Step 5: Implement deterministic patch reconstruction**

Use one pure helper:

```python
def apply_patches(base: str, patches: list[RevisionPatch]) -> str:
    ordered = sorted(patches, key=lambda item: item.start_offset)
    cursor = 0
    pieces: list[str] = []
    for patch in ordered:
        if patch.start_offset < cursor or patch.end_offset < patch.start_offset:
            raise BadRequest(message="修改片段重叠或范围无效")
        if base[patch.start_offset:patch.end_offset] != patch.original_text:
            raise BadRequest(message="修改片段与当前正文不匹配")
        pieces.append(base[cursor:patch.start_offset])
        pieces.append(patch.replacement_text)
        cursor = patch.end_offset
    pieces.append(base[cursor:])
    return "".join(pieces)
```

Require reconstructed content to equal `candidate_content`. Compute SHA-256 in the service rather than trusting the Agent.

For scope enforcement, locate `issue.location` in the base content and allow a 300-character context window on each side. Any patch outside that window forces `expanded_scope=true`; a missing expansion reason rejects the output.

- [ ] **Step 6: Persist options and candidates only after all validation passes**

`generate_options()` stores `repair_options_json` on the open issue only after complete validation. `create_revision()`:

1. validates owned open issue and current mutable version;
2. resolves selected option or custom intent;
3. calls the Agent;
4. validates patches, result and scope;
5. sets `sequence=0` because rejected or superseded candidates do not consume the author-visible R numbering;
6. sets `source_type="review_issue"`, `source_id=issue.id`, current base sequence/hash, and `status="candidate"`;
7. commits without changing current content or issue status.

- [ ] **Step 7: Run tests and commit**

```sh
.venv/bin/python -m pytest tests/test_phase_4_modification.py -x -q
git add backend/app/ai/modification.py backend/app/services/modification_service.py backend/tests/test_phase_4_modification.py backend/tests/test_phase_4_ai_integration.py
git commit -m "feat: generate validated local revision candidates"
```

---

### Task 7: Apply/reject candidates atomically and unify Phase 2/3 repair paths

**Files:**

- Modify: `backend/app/services/draft_version_service.py`
- Modify: `backend/app/services/plot_planning_service.py`
- Modify: `backend/app/services/repair_service.py`
- Modify: `backend/app/repositories/plot_planning_repo.py`
- Modify: `backend/app/repositories/quality_gate_repo.py`
- Modify: `backend/app/api/planning.py`
- Modify: `backend/app/api/writing.py`
- Modify: `backend/tests/test_phase_2_quality_gate.py`
- Modify: `backend/tests/test_phase_3_dynamic_plot_planning.py`
- Modify: `backend/tests/test_phase_4_modification.py`

**Interfaces:**

```python
DraftVersionService.apply_revision(
    revision_id: int,
    confirm_expanded_scope: bool = False,
) -> tuple[DraftVersion, DraftRevision]
DraftVersionService.reject_revision(revision_id: int) -> DraftRevision
```

- [ ] **Step 1: Write the atomic state-transition matrix as failing tests**

Cover:

- apply updates DraftVersion and WritingRun, increments only `revision_sequence`, and leaves `version` unchanged;
- reject leaves both contents unchanged and keeps a ReviewIssue open;
- apply marks source ReviewIssue resolved and sets `resolved_by_revision_id`;
- apply supersedes sibling candidates from the same base;
- stale sequence, stale hash, patch mismatch, unconfirmed expanded scope, non-draft version, accepted/discarded run, locked chapter, cross-novel revision and database exception all preserve prior state;
- planning candidate application clears `planning_blocked` and returns `decision_required → completed`;
- applying a candidate linked to PendingRepair marks it applied and recomputes `has_pending_repairs`.

- [ ] **Step 2: Run and confirm RED**

```sh
.venv/bin/python -m pytest tests/test_phase_4_modification.py tests/test_phase_3_dynamic_plot_planning.py -x -q
```

- [ ] **Step 3: Implement the single transaction apply path**

Inside `begin_nested()`:

1. Load owned candidate and its DraftVersion/RunningRun.
2. Verify mutable status and unlocked chapter.
3. Verify sequence and hash.
4. Reconstruct candidate from stored patches and compare stored candidate.
5. Require expansion confirmation when needed.
6. Set the selected revision sequence and DraftVersion revision sequence to `current revision_sequence + 1`, then update DraftVersion content/word count.
7. Synchronize WritingRun content/word count.
8. Mark selected candidate applied.
9. Mark exact-base sibling candidates superseded.
10. Resolve linked ReviewIssue and PendingRepair when applicable.
11. Clear Phase 3 planning block for `source_type=planning_decision`.

Commit once after the nested transaction. On `IntegrityError` or any business failure, roll back and re-raise without mutating in-memory response objects.

- [ ] **Step 4: Delegate Phase 3 candidate creation and application**

When `PlotPlanningService.choose_decision()` creates a DraftRevision, it first obtains the current v1/current version and sets all Phase 4 fields. It may still use the existing Phase 3 `LocalRevisionOutput`, but must convert its full-content diff to an exact patch and validate it before persistence.

Replace `PlotPlanningService.apply_draft_revision()` implementation with a call to `DraftVersionService.apply_revision()`. Keep `PUT /draft-revisions/{revision_id}/apply` at its existing path and return the unified `DraftRevisionOut` so existing clients continue to work.

- [ ] **Step 5: Turn PendingRepair apply into candidate generation**

`QualityGateService` will link new PendingRepair rows to ReviewIssue in Task 8. Change compatibility behavior now:

- `dismiss`: call `ModificationService.ignore_issue()` with `intent_text` as the reason, then mark PendingRepair dismissed;
- `apply`: call `ModificationService.create_revision()` and return the candidate; do not alter WritingRun and do not mark PendingRepair applied yet;
- candidate application later marks PendingRepair applied through `review_issue_id`.

Change the compatibility resolve response to include `{pending_repair, draft_revision}`. Existing callers that ignore `data` remain compatible.

`RepairService.__init__` 将 `generator` 参数替换为可注入的 `modification_agent: BaseModificationAgent | None = None`，默认创建 `DeepSeekModificationAgent`；受影响的 Phase 2 测试全部注入 `FakeModificationAgent`。

- [ ] **Step 6: Run Phase 2–4 regressions and commit**

```sh
.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py tests/test_phase_3_dynamic_plot_planning.py tests/test_phase_4_modification.py -x -q
git add backend/app/services backend/app/repositories backend/app/api backend/tests
git commit -m "refactor: unify draft revision application"
```

---

### Task 8: Separate ReviewIssue severity from resolution mode

**Files:**

- Modify: `backend/app/ai/quality_gate.py`
- Modify: `backend/app/ai/quality_agents.py`
- Modify: `backend/app/ai/plot_planning.py`
- Modify: `backend/app/ai/writer.py`
- Modify: `backend/app/services/quality_gate_service.py`
- Modify: `backend/app/services/writing_service.py`
- Modify: `backend/app/repositories/quality_gate_repo.py`
- Modify: `backend/tests/test_phase_2_quality_gate.py`
- Modify: `backend/tests/test_phase_3_dynamic_plot_planning.py`
- Modify: `backend/tests/test_phase_4_modification.py`

**Interfaces:**

```python
class CheckResult(BaseModel):
    passed: bool
    issue_type: str
    severity: Literal["blocking", "major", "minor"]
    resolution_mode: Literal["auto_fixable", "needs_intent"]
    ...
```

- [ ] **Step 1: Rewrite failing quality-gate tests around the two dimensions**

Representative cases:

```python
CheckResult(
    passed=False,
    issue_type="style",
    severity="major",
    resolution_mode="auto_fixable",
    fix_strategy="full_rewrite",
)

CheckResult(
    passed=False,
    issue_type="character",
    severity="blocking",
    resolution_mode="needs_intent",
    options=[{"label": "保持谨慎", "summary": "补充犹豫动机"}],
)
```

Assert that `major + auto_fixable` requests internal rewrite, while `blocking + needs_intent` creates an open ReviewIssue and linked PendingRepair. Severity alone never selects a repair strategy.

- [ ] **Step 2: Run and confirm RED**

```sh
.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py tests/test_phase_3_dynamic_plot_planning.py -x -q
```

- [ ] **Step 3: Update the AI protocol and prompt**

`quality_agents.py` validates independent allowed sets. Prompt output fields state:

- severity assesses impact: blocking, major, minor;
- resolution_mode assesses author involvement: auto_fixable, needs_intent;
- `fix_strategy` is legal only for auto_fixable;
- options/intent type are legal only for needs_intent.

Update FakeQualityGateAgent passing results to `severity="minor", resolution_mode="auto_fixable"`.

Define a typed `QualityIssueOutput` inside `ai.plot_planning` with the same severity/resolution values and change `DraftReviewOutput.quality_issues` from `list[dict]` to `list[QualityIssueOutput]`. Update the DeepSeek review prompt accordingly.

- [ ] **Step 4: Create ReviewIssue before PendingRepair**

`QualityGateService.run()` first persists ReviewIssue, then:

- internal `full_rewrite` and `local_replace` behavior remains generation-internal and occurs before v1;
- a successful internal `local_replace` immediately marks its ReviewIssue `resolved` with no DraftRevision, because v1 does not yet exist;
- a `full_rewrite` issue stays open only when the retry budget is exhausted; when another retry runs, the existing cleanup path removes the obsolete issue before the next check;
- `needs_intent` creates PendingRepair with `review_issue_id=issue.id` and `chapter_id=run.target_chapter_id`（never the sentinel value 0）;
- `acceptance_blocking = severity == "blocking"` is maintained only for compatibility;
- snapshot reports counts by severity and resolution mode.

`WritingService.review_writing_run()` accepts only unaccepted working runs, creates typed ReviewIssues, and never permits Phase 4 edits after acceptance.

- [ ] **Step 5: Run regressions and commit**

```sh
.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py tests/test_phase_3_dynamic_plot_planning.py tests/test_phase_4_modification.py -x -q
git add backend/app/ai backend/app/services/quality_gate_service.py backend/app/services/writing_service.py backend/app/repositories/quality_gate_repo.py backend/tests
git commit -m "refactor: separate review severity and resolution mode"
```

---

### Task 9: Expose Phase 4 APIs with ownership-safe dependency injection

**Files:**

- Create: `backend/app/api/revisions.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/writing.py`
- Modify: `backend/app/api/planning.py`
- Create: `backend/tests/test_phase_4_api.py`

**Interfaces:**

```text
GET  /api/v1/novels/{novel_id}/writing-runs/{run_id}/draft-versions
GET  /api/v1/novels/{novel_id}/draft-versions/{version_id}
POST /api/v1/novels/{novel_id}/writing-runs/{run_id}/draft-versions
POST /api/v1/novels/{novel_id}/draft-versions/{version_id}/restore-into-current
POST /api/v1/novels/{novel_id}/writing-runs/{run_id}/manual-revisions

GET  /api/v1/novels/{novel_id}/writing-runs/{run_id}/review-issues
POST /api/v1/novels/{novel_id}/review-issues/{issue_id}/repair-options
POST /api/v1/novels/{novel_id}/review-issues/{issue_id}/draft-revisions
PUT  /api/v1/novels/{novel_id}/review-issues/{issue_id}/ignore
GET  /api/v1/novels/{novel_id}/draft-versions/{version_id}/draft-revisions
PUT  /api/v1/novels/{novel_id}/draft-revisions/{revision_id}/apply
PUT  /api/v1/novels/{novel_id}/draft-revisions/{revision_id}/reject
```

- [ ] **Step 1: Write HTTP contract tests before routes**

Test every success path plus:

- missing authentication returns 401;
- another user's novel/version/issue/revision returns 404;
- version from another run cannot be used as a base;
- stale revision sequence returns a 400 ApiResponse;
- invalid option/custom intent body returns 422;
- expanded candidate without confirmation returns 400;
- accepted/discarded/locked writes return 400;
- all success responses have `code=0`, `message`, and typed `data`.

Override the ModificationService provider in API tests with a FakeModificationAgent; never monkeypatch HTTP/network functions.

- [ ] **Step 2: Run and confirm RED**

```sh
.venv/bin/python -m pytest tests/test_phase_4_api.py -x -q
```

- [ ] **Step 3: Implement route dependency providers**

Expose testable providers:

```python
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
```

API tests override `get_modification_service` and clear the override in fixture teardown.

- [ ] **Step 4: Implement routes and compatibility responses**

Use `DraftVersionOut`, `DraftRevisionOut`, `ReviewIssueOut`, and `RepairOptionOut` for every response. Register `revisions.router` in `main.py` under `/api/v1`.

从 `api/planning.py` 删除 Phase 3 的 apply 路由定义，由 `api/revisions.py` 独占同一个 `PUT /draft-revisions/{revision_id}/apply` URL；Phase 3 客户端路径不变，状态转换实现只有 `DraftVersionService.apply_revision()` 一处。

- [ ] **Step 5: Run API and service tests, then commit**

```sh
.venv/bin/python -m pytest tests/test_phase_4_api.py tests/test_phase_4_draft_versions.py tests/test_phase_4_modification.py -x -q
git add backend/app/api backend/app/main.py backend/tests/test_phase_4_api.py
git commit -m "feat: expose assisted revision APIs"
```

---

### Task 10: Add frontend revision types, API client, and Pinia store

**Files:**

- Create: `frontend/src/types/revision.ts`
- Create: `frontend/src/api/revisions.ts`
- Create: `frontend/src/stores/revisions.ts`
- Modify: `frontend/src/types/writing.ts`
- Modify: `frontend/src/types/plotPlanning.ts`
- Modify: `frontend/src/api/writing.ts`
- Modify: `frontend/src/api/planning.ts`
- Modify: `frontend/src/stores/writing.ts`
- Modify: `frontend/src/stores/plotPlanning.ts`
- Create: `frontend/src/__tests__/WritingWorkspacePhase4.spec.ts`

**Interfaces:**

```typescript
type DraftVersionStatus = 'draft' | 'accepted' | 'rejected' | 'archived'
type DraftRevisionStatus = 'candidate' | 'applied' | 'rejected' | 'superseded'
type DraftRevisionSource =
  | 'planning_decision'
  | 'review_issue'
  | 'author_request'
  | 'manual_edit'
  | 'restore'
type ReviewIssueSeverity = 'blocking' | 'major' | 'minor'
type ReviewIssueResolutionMode = 'auto_fixable' | 'needs_intent'
```

- [ ] **Step 1: Write failing store contract tests**

Mock `@/api/revisions` and assert:

- `loadWorkspace()` loads versions, selects the current draft, then loads its revisions and run issues;
- generating options updates only the selected issue;
- generating a candidate does not change `currentVersion.content`;
- apply replaces the current version from the server and refreshes issues/revisions;
- reject leaves content unchanged and refreshes revision status;
- createVersion is the only action that makes `currentVersion.version` increase;
- manual save and restore keep the same version number;
- failed requests preserve candidate, option selection, custom intent, and editor content.

- [ ] **Step 2: Run and confirm RED**

```sh
npm run test:unit -- src/__tests__/WritingWorkspacePhase4.spec.ts
```

Expected RED: modules do not exist.

- [ ] **Step 3: Define complete TypeScript contracts**

`DraftVersion`, `DraftRevision`, `RevisionPatch`, `ReviewIssue`, `RepairOption`, and all request payloads mirror backend field names exactly. `DraftRevision.draft_version_id` is `number | null` only for legacy rows. Re-export `DraftRevision` from `types/plotPlanning.ts` to avoid breaking current Phase 3 imports, then migrate new code to `types/revision.ts`.

Change `acceptWritingRun()` to accept an optional `{ force_accept: boolean; force_reason?: string }` and always send `{}` when normal accepting, avoiding an ambiguous no-body request.

- [ ] **Step 4: Implement API functions for every Phase 4 route**

Use explicit return types. Important signatures:

```typescript
listDraftVersions(novelId: number, runId: number): Promise<DraftVersion[]>
createDraftVersion(novelId: number, runId: number, payload: CreateDraftVersionRequest): Promise<DraftVersion>
saveManualRevision(novelId: number, runId: number, payload: ManualRevisionRequest): Promise<RevisionMutationResponse>
restoreVersion(novelId: number, versionId: number, payload: RestoreVersionRequest): Promise<RevisionMutationResponse>
listReviewIssues(novelId: number, runId: number): Promise<ReviewIssue[]>
generateRepairOptions(novelId: number, issueId: number): Promise<RepairOption[]>
createRevisionCandidate(novelId: number, issueId: number, payload: CreateRevisionRequest): Promise<DraftRevision>
applyRevision(novelId: number, revisionId: number, confirmExpandedScope: boolean): Promise<RevisionMutationResponse>
rejectRevision(novelId: number, revisionId: number): Promise<DraftRevision>
```

- [ ] **Step 5: Implement a dedicated revision store**

State:

```typescript
const versions = ref<DraftVersion[]>([])
const currentVersion = ref<DraftVersion | null>(null)
const revisions = ref<DraftRevision[]>([])
const reviewIssues = ref<ReviewIssue[]>([])
const selectedIssueId = ref<number | null>(null)
const selectedOptionIndex = ref<number | null>(null)
const customIntent = ref('')
const candidate = ref<DraftRevision | null>(null)
const loading = ref(false)
```

No optimistic content mutation is allowed. Every successful state change uses server-returned DraftVersion/Revision objects. Errors are rethrown after `loading` resets so the view can show an Element Plus message without losing form state.

Change `plotPlanningStore.applyDraftRevision()` to call the canonical revisions API/store and remove its local candidate only after server success. Keep `writingStore` focused on WritingRun and acceptance.

- [ ] **Step 6: Run tests/type-check and commit**

```sh
npm run test:unit -- src/__tests__/WritingWorkspacePhase4.spec.ts
npm run type-check
git add frontend/src/types frontend/src/api frontend/src/stores frontend/src/__tests__/WritingWorkspacePhase4.spec.ts
git commit -m "feat: add assisted revision frontend data layer"
```

---

### Task 11: Build the three-level revision workspace UI

**Files:**

- Create: `frontend/src/components/writing/ReviewIssuePanel.vue`
- Create: `frontend/src/components/writing/RevisionCandidatePanel.vue`
- Create: `frontend/src/components/writing/DraftVersionTimeline.vue`
- Create: `frontend/src/components/writing/RevisionHistoryPanel.vue`
- Modify: `frontend/src/components/writing/DraftRevisionDiff.vue`
- Modify: `frontend/src/views/novels/WritingWorkspaceView.vue`
- Modify: `frontend/src/__tests__/WritingWorkspacePhase4.spec.ts`
- Modify: `frontend/src/__tests__/WritingWorkspacePhase3.spec.ts`
- Modify: `frontend/src/__tests__/PlotPlanning.spec.ts`

**Interfaces:**

- `ReviewIssuePanel` emits `generate-options`, `create-candidate`, `ignore`.
- `RevisionCandidatePanel` emits `apply`, `reject`, and requests explicit confirmation for expanded scope.
- `DraftVersionTimeline` emits `create-version`, `restore`, `select-version`.
- `RevisionHistoryPanel` is read-only and distinguishes applied/rejected/superseded candidates.
- `DraftRevisionDiff` consumes the unified revision type and renders exact patches with surrounding context.

- [ ] **Step 1: Add failing component interaction tests**

Tests assert the visible language and event boundary:

- initial workspace displays `当前版本 v1` and no v2;
- R1/R2 appear under `内部修改`, never under `版本历史`;
- `创建新版本` opens a dialog requiring base version and reason;
- after server returns v2, timeline shows `v2（当前）` and `v1（已归档）`;
- candidate generation does not change editor content;
- patch diff displays deletion/addition and change reason;
- reject leaves issue open;
- expanded scope shows a second confirmation containing the Agent's reason;
- restore dialog states that it will modify the current version without creating v3;
- locked/accepted/discarded runs disable all Phase 4 actions;
- API failure preserves editor text and option/custom-intent inputs.

- [ ] **Step 2: Run and confirm RED**

```sh
npm run test:unit -- src/__tests__/WritingWorkspacePhase4.spec.ts
```

- [ ] **Step 3: Implement ReviewIssue and candidate panels**

The issue panel groups by severity, shows resolution mode, and permits one selected issue at a time. It renders saved options plus custom intent and never labels options as versions.

The candidate panel shows:

- source and reason;
- base revision sequence;
- every patch's old/new text and local context;
- expanded-scope warning;
- Apply and Reject actions.

Applying uses `ElMessageBox.confirm` only when expanded; normal local candidates apply directly after the author's button click.

- [ ] **Step 4: Implement separate internal history and version timeline**

Required display hierarchy:

```text
当前版本：v1 首次生成
内部修改：
  R2 手动编辑：补充角色动机
  R1 ReviewIssue：保持谨慎人设

版本历史：
  v2 节奏调整（当前）
  v1 首次生成（已归档）
```

Do not show generation retries as R entries because they occurred before v1 was established. Historical version selection is read-only. Restore always targets the current draft and refreshes both current content and internal history.

- [ ] **Step 5: Integrate the workspace and acceptance guard**

`WritingWorkspaceView` loads Phase 4 data when a run is selected. The editor buffer tracks current version content; Save creates one manual applied revision, not a new version.

On accept:

- if open blocking issues exist, show a force-accept dialog with a required reason;
- pending candidates route the user to the candidate panel and do not offer force bypass;
- after success, mark the workspace read-only and show extraction result.

Phase 3 decision cards still create candidates, but their diff and apply action use the Phase 4 candidate panel/store.

- [ ] **Step 6: Run frontend verification and commit**

```sh
npm run test:unit
npm run type-check
npm run lint
npm run build
git add frontend/src/components/writing frontend/src/views/novels/WritingWorkspaceView.vue frontend/src/__tests__
git commit -m "feat: add phase 4 revision workspace"
```

---

### Task 12: Prove the full Phase 4 acceptance path and close regressions

**Files:**

- Create: `backend/tests/test_phase_4_acceptance.py`
- Modify: `backend/tests/test_phase_4_api.py`
- Modify: `backend/tests/test_phase_4_models_and_migration.py`
- Modify: `frontend/src/__tests__/WritingWorkspacePhase4.spec.ts`
- Modify: `docs/superpowers/specs/2026-07-13-v2-phase-4-assisted-revision-design.md` only if implementation reveals a confirmed contract correction

**Interfaces:**

- One deterministic acceptance test executes the complete flow with FakeWritingGenerator, staged FakeQualityGateAgent, FakeModificationAgent, and FakeExtractionService.
- No default test invokes real DeepSeek.

- [ ] **Step 1: Write the complete failing backend acceptance test**

The test performs and asserts this exact sequence:

```text
1. Generate initial draft with expansion and two quality-gate rewrites.
2. Assert exactly one DraftVersion v1 and revision_sequence 0.
3. Review and create an open ReviewIssue.
4. Generate multiple repair directions.
5. Generate candidate A and assert v1 content unchanged.
6. Reject candidate A and assert issue remains open.
7. Generate/apply candidate B; assert R1 applied and version still v1.
8. Manually save content; assert R2 applied and version still v1.
9. Explicitly create a new version based on v1; assert exactly v2 is current.
10. Restore v1 into v2; assert a restore revision exists and version remains v2.
11. Resolve/ignore remaining blocking issues.
12. Accept v2; assert Chapter content equals v2, version accepted, PendingMemory extraction called once.
13. Publish Chapter to locked.
14. Assert create version, restore, manual save and candidate apply all fail.
```

- [ ] **Step 2: Run the acceptance test and fix only observed integration gaps**

```sh
.venv/bin/python -m pytest tests/test_phase_4_acceptance.py -x -q
```

Expected final GREEN: complete scenario passes without network.

- [ ] **Step 3: Run the full deterministic backend suite**

```sh
.venv/bin/python -m pytest tests/ -x -q
```

Expected: all deterministic tests pass, live tests are deselected, and output contains no DeepSeek network error.

- [ ] **Step 4: Verify migration upgrade and downgrade on a disposable SQLite database**

Run the subprocess-based test created in Task 2:

```sh
.venv/bin/python -m pytest tests/test_phase_4_models_and_migration.py -k migration_round_trip -x -q
```

Expected: the test upgrades a `tmp_path` database from Phase 3, verifies v1 and legacy-field backfill, downgrades once, upgrades again, and passes without touching the development or standard test database.

- [ ] **Step 5: Run the complete frontend suite**

```sh
npm run test:unit
npm run type-check
npm run lint
npm run build
```

Expected: all commands pass.

- [ ] **Step 6: Optionally run the explicit live modification-agent check**

Only when a valid key is intentionally available:

```sh
.venv/bin/python -m pytest -o addopts='' -m integration tests/test_phase_4_ai_integration.py -x -q
```

This result is recorded separately and is not required for deterministic suite success.

- [ ] **Step 7: Review spec coverage and eliminate ambiguity**

Search for forbidden or stale semantics:

```sh
rg -n "v2.*自动|自动.*v2|版本.*局部修改|severity.*auto_fixable|severity.*needs_intent" backend frontend docs/superpowers
rg -n "draft_content\s*=|\.draft_content\s*=" backend/app/services
```

Expected:

- no UI or service describes internal repair as a new DraftVersion;
- only generation-internal code and DraftVersionService write `WritingRun.draft_content`;
- no business branch uses severity to mean resolution mode;
- Phase 3 and RepairService no longer directly apply candidate content.

- [ ] **Step 8: Commit closure**

```sh
git add backend/tests/test_phase_4_acceptance.py backend/tests/test_phase_4_api.py backend/tests/test_phase_4_models_and_migration.py frontend/src/__tests__/WritingWorkspacePhase4.spec.ts docs/superpowers/specs/2026-07-13-v2-phase-4-assisted-revision-design.md
git commit -m "test: close phase 4 assisted revision acceptance"
```

## Final Verification Checklist

- [ ] `DraftVersion v1` is created once, after internal generation converges.
- [ ] Internal AI fixes, local repairs, manual edits and restore operations never increment `DraftVersion.version`.
- [ ] Only the explicit create-version API produces v2+.
- [ ] Candidate generation never changes the current正文 or resolves its issue.
- [ ] Candidate apply is atomic, stale-safe, lock-safe and scope-confirmed.
- [ ] Phase 2 PendingRepair and Phase 3 PlanningDecision use the same DraftRevision apply path.
- [ ] Accepted/discarded WritingRuns cannot create or mutate versions.
- [ ] Acceptance uses current DraftVersion content and keeps PendingMemory extraction aligned.
- [ ] Frontend distinguishes current version, internal revisions and version history.
- [ ] Default backend tests are Python 3.12, deterministic and offline.
- [ ] Backend full suite, Alembic round trip, frontend tests, type-check, lint and build all pass.
