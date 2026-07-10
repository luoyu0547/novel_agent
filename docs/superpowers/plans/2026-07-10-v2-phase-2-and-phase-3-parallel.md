# V2 Phase 2 + Phase 3 Parallel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏现有单章自主写作闭环的前提下，同时补齐 Phase 2 的真实质量门禁与记忆回写，并完成 Phase 3 的卷级结构、计划版本和长篇推进管理。

**Architecture:** 先冻结 Phase 2 与 Phase 3 共用的数据契约：写作运行保存规划版本快照，质量检查统一输出可追踪的问题，计划实体通过版本记录保持历史。Phase 2 负责“草稿是否可靠以及如何修复”，Phase 3 负责“本章为什么存在以及如何服务长线结构”；两条线分别改动质量门禁和规划模块，最后通过 `WritingRun`、`ContextPackage` 和记忆提取流程集成。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, Pydantic v2, LangChain/DeepSeek, Vue 3, TypeScript, Pinia, Element Plus, pytest, Vitest。

## Global Constraints

- 所有接口继续挂在 `/api/v1/novels/{novel_id}/` 下，并验证当前用户对小说的所有权。
- 所有接口继续使用 `ApiResponse.success()` / `ApiResponse.error()` 统一响应格式。
- AI 只能生成蓝图、规划、草稿、检查结果和记忆候选；正式正文和正式记忆仍需作者确认。
- Phase 2 的自动修复必须记录 `RepairLog`，需要作者意图的修复必须记录 `PendingRepair`。
- Phase 3 的旧规划不能被覆盖；任何激活、修改或废弃动作都必须保留可追溯版本。
- `WritingRun` 必须保存本次使用的规划版本和上下文快照，确保后续修改不会改变历史解释。
- 不在本计划中引入向量数据库、批量连续写作或自动生成整本小说。
- 后端测试命令为 `.venv/bin/python -m pytest tests/ -x -q`；前端验证命令为 `npm run type-check`, `npm run test:unit`, `npm run build`。

---

## Task 1: Freeze shared planning, review, and run contracts

**Files:**
- Modify: `backend/app/models/writing.py`
- Modify: `backend/app/schemas/writing.py`
- Create: `backend/app/models/planning.py`
- Create: `backend/app/schemas/planning.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `frontend/src/types/writing.ts`
- Create: `frontend/src/types/planning.ts`
- Test: `backend/tests/test_phase_2_quality_gate.py`
- Test: `backend/tests/test_phase_3_planning.py`
- Create: `backend/alembic/versions/<generated>_v2_phase_2_3_shared_contracts.py`

**Interfaces:**
- Produces `VolumeArc`, `PlanVersion`, and `ReviewIssue` contracts for later tasks.
- Extends `WritingRun` with `mode`, `target_word_count`, `min_word_count`, `max_word_count`, `input_snapshot`, `agent_notes`, `self_check`, and `plan_version_ids` inside the existing JSON snapshot strategy.
- Changes `PendingRepair.chapter_id` to nullable until a draft is accepted into a real chapter; the writing run remains the source of ownership before acceptance.

- [ ] **Step 1: Write failing model and schema tests**

  Add tests that create a volume arc, a plan version, and a review issue; assert their ownership fields, status values, JSON snapshots, and Pydantic serialization. Add a test that creates a new-chapter `WritingRun` with a pending repair whose `chapter_id` is `None`.

- [ ] **Step 2: Run the focused tests and verify failure**

  Run: `.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py tests/test_phase_3_planning.py -x -q`

  Expected: collection or model import failures because the new planning models and fields do not exist.

- [ ] **Step 3: Add the shared models and migration**

  Implement `VolumeArc` with `novel_id`, `blueprint_id`, `order_index`, `title`, `goal`, `start_state`, `end_state`, `key_events`, `pacing_notes`, `foreshadowing_plan`, and `status`. Implement `PlanVersion` with `novel_id`, `plan_type`, `plan_id`, `version`, `change_reason`, `impact_scope`, `snapshot_json`, and `status`. Implement `ReviewIssue` with `novel_id`, optional `writing_run_id`, issue type, severity, location, description, related memory, suggestion, acceptance blocking flag, and status.

  Add an Alembic migration instead of changing the initial migrations. Update model exports and frontend types with the same field names and status unions.

- [ ] **Step 4: Run focused tests and migration checks**

  Run: `.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py tests/test_phase_3_planning.py -x -q`

  Run: `.venv/bin/python -m alembic upgrade head`

  Expected: model tests pass and the new tables/columns are present.

- [ ] **Step 5: Commit the shared contract**

  Run: `git add backend/app/models backend/app/schemas backend/alembic/versions frontend/src/types && git commit -m "feat: define shared phase 2 and phase 3 contracts"`

## Task 2: Implement real Phase 2 quality checks

**Files:**
- Create: `backend/app/ai/quality_agents.py`
- Modify: `backend/app/ai/quality_gate.py`
- Modify: `backend/app/services/quality_gate_service.py`
- Modify: `backend/app/services/writing_service.py`
- Test: `backend/tests/test_phase_2_quality_gate.py`

**Interfaces:**
- Consumes `WritingRun`, `ChapterBrief`, `ContextPackage`, active `PlanVersion`, and the existing `CheckResult` shape.
- Produces `DeepSeekQualityGateAgent.check(draft, brief, context_package) -> list[CheckResult]` with checks for task completion, style/readability, character continuity, plot continuity, world consistency, foreshadowing, and length/content density.
- Preserves `FakeQualityGateAgent` for unit tests and allows `WritingService(gate_agent=...)` injection.

- [ ] **Step 1: Add failing tests for non-trivial check results**

  Add a fake agent test returning one `needs_intent` character issue and one `auto_fixable` style issue. Assert that the service creates the correct repair records, keeps issue location/context, and returns `has_pending_repairs=True`.

  Add an agent contract test asserting every result has one of the allowed issue types and severities, and that a malformed model response is converted into a failed gate result rather than crashing the writing run.

- [ ] **Step 2: Run the focused tests and verify failure**

  Run: `.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py -x -q`

  Expected: failures because the real agent and malformed-result handling are not implemented.

- [ ] **Step 3: Implement sequential real quality agents**

  Add one explicit checker per quality dimension behind a common protocol. Each checker receives only the draft, brief, context, and its quality rubric; each returns one or more `CheckResult` objects. Invoke them sequentially so a failing check can be logged and debugged without concurrent model calls.

  The DeepSeek adapter must request structured JSON, validate with Pydantic, ignore unknown fields, and return `gated=False` on provider/parse failure. Do not make the real provider the test default; tests continue to inject `FakeQualityGateAgent`.

- [ ] **Step 4: Integrate issue persistence and gate result snapshots**

  Update `QualityGateService.run()` to persist `ReviewIssue` for every failed check, then route objective repairs to `RepairLog` and creative choices to `PendingRepair`. Recompute `gate_result_json` after every rewrite iteration and stop after three iterations. A provider failure must leave the draft available with `gated=False` and a diagnostic error.

- [ ] **Step 5: Run the quality gate tests**

  Run: `.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py -x -q`

  Expected: PASS, including all-pass, auto-fix, needs-intent, malformed response, provider failure, and three-iteration limit cases.

- [ ] **Step 6: Commit Phase 2 quality checking**

  Run: `git add backend/app/ai backend/app/services backend/tests/test_phase_2_quality_gate.py && git commit -m "feat: implement real phase 2 quality gate checks"`

## Task 3: Make PendingRepair resolution actually apply intent

**Files:**
- Modify: `backend/app/ai/writer.py`
- Create: `backend/app/services/repair_service.py`
- Modify: `backend/app/api/writing.py`
- Modify: `frontend/src/stores/writing.ts`
- Modify: `frontend/src/components/editor/RepairItem.vue`
- Test: `backend/tests/test_phase_2_quality_gate.py`
- Test: `frontend/src/__tests__/WritingEditor.spec.ts`

**Interfaces:**
- Produces `RepairService.resolve(novel_id, repair_id, action, choice_index, intent_text) -> PendingRepair`.
- Extends `BaseWritingGenerator` with `rewrite_fragment(draft, location, context, intent) -> str`.
- The endpoint remains `PUT /api/v1/novels/{novel_id}/writing/repairs/{repair_id}/resolve`.

- [ ] **Step 1: Write failing API and component tests**

  Assert that applying a choice calls the fragment rewrite path, updates the `WritingRun.draft_content`, records a new repair log, and marks the item `applied`. Assert that dismissing an item leaves draft content unchanged. Assert that the frontend refreshes the run and removes only the resolved pending item.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py -x -q`

  Expected: the current endpoint only changes status, so the content and repair-log assertions fail.

- [ ] **Step 3: Implement the repair service**

  Move ownership, status, action, choice-index, and intent-text validation into `RepairService`. For `apply`, load the associated run, call the injected generator, save the rewritten draft and a `RepairLog`, then mark the pending item applied. For `dismiss`, save only the status transition. Reject cross-novel repairs and already-resolved items.

- [ ] **Step 4: Update frontend state and interaction**

  After resolving, reload the affected run and repairs from the API. Keep the sidebar visible while unresolved items remain; remove the item from the pending list after applied/dismissed. Show provider errors without losing the pending item.

- [ ] **Step 5: Run backend and frontend focused tests**

  Run: `.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py -x -q`

  Run: `npm run test:unit -- src/__tests__/WritingEditor.spec.ts`

- [ ] **Step 6: Commit repair execution**

  Run: `git add backend/app backend/tests/test_phase_2_quality_gate.py frontend/src && git commit -m "feat: apply pending repair intent to writing drafts"`

## Task 4: Close the Phase 2 to memory feedback loop

**Files:**
- Modify: `backend/app/services/writing_service.py`
- Modify: `backend/app/ai/service.py`
- Modify: `backend/app/api/writing.py`
- Modify: `frontend/src/views/novels/WritingWorkspaceView.vue`
- Modify: `frontend/src/stores/pendingMemory.ts`
- Test: `backend/tests/test_phase_2_quality_gate.py`
- Test: `backend/tests/test_phase_2_ai_extract.py`

**Interfaces:**
- Produces `POST /api/v1/novels/{novel_id}/writing-runs/{run_id}/accept` behavior that accepts the draft, invokes memory extraction for the accepted chapter, and returns the chapter plus pending-memory summary.
- Keeps extraction results in `PendingMemory`; no extraction result is directly written into formal memory without confirmation.

- [ ] **Step 1: Write failing acceptance-to-memory tests**

  Use an injected extraction fake and assert that accepting a new chapter invokes extraction exactly once with the created chapter id. Assert that an existing target chapter uses that chapter id. Assert that extraction failure does not roll back the accepted正文 and returns a visible pending-memory error state.

- [ ] **Step 2: Run the focused tests and verify failure**

  Run: `.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py tests/test_phase_2_ai_extract.py -x -q`

  Expected: the current accept endpoint writes the chapter but never invokes extraction.

- [ ] **Step 3: Implement the post-accept hook**

  Add an injectable extraction service to `WritingService`. Commit the chapter and run status before invoking the extraction hook so accepted正文 is durable. Return the created pending ids/count in the API response and keep the existing standalone extraction endpoint unchanged.

- [ ] **Step 4: Update the workspace handoff**

  After acceptance, navigate to the pending-memory view or display a link/count in the writing workspace. Refresh pending-memory state so the author can confirm or reject candidates immediately.

- [ ] **Step 5: Run the focused tests and commit**

  Run: `.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py tests/test_phase_2_ai_extract.py -x -q`

  Run: `git add backend/app frontend/src backend/tests && git commit -m "feat: extract pending memories after draft acceptance"`

## Task 5: Implement Phase 3 volume arcs and plan versions

**Files:**
- Create: `backend/app/repositories/planning_repo.py`
- Create: `backend/app/services/planning_service.py`
- Create: `backend/app/api/planning.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/models/novel.py`
- Modify: `backend/app/models/planning.py`
- Modify: `backend/app/schemas/planning.py`
- Test: `backend/tests/test_phase_3_planning.py`

**Interfaces:**
- Produces CRUD and activation APIs for volume arcs and plan versions under `/api/v1/novels/{novel_id}/planning/`.
- Produces `PlanningService.create_volume_arc()`, `list_volume_arcs()`, `update_volume_arc()`, `activate_volume_arc()`, `create_plan_version()`, `list_plan_versions()`, and `activate_plan_version()`.
- Every update creates a new version snapshot; an archived plan version cannot be activated without creating a new version.

- [ ] **Step 1: Write failing service/API tests**

  Test creation and ownership of volume arcs, ordering by `order_index`, activation of one active arc, version creation with change reason and impact scope, activation of a current version, and cross-user 404 protection.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `.venv/bin/python -m pytest tests/test_phase_3_planning.py -x -q`

  Expected: import or route failures because the planning repository, service, and router do not exist.

- [ ] **Step 3: Implement repository and service layers**

  Follow the existing `api -> services -> repositories -> models` flow. Every repository query must filter by the resource id and every service mutation must first validate the owned novel. Use transaction-local uniqueness checks for one active plan version per plan entity.

- [ ] **Step 4: Implement the planning router and register it**

  Add endpoints for volume-arc CRUD, plan-version listing/creation/activation, and a planning dashboard response that returns the active blueprint, active volume arcs, current chapter plans, open review issues, and unresolved foreshadowings.

- [ ] **Step 5: Run backend planning tests**

  Run: `.venv/bin/python -m pytest tests/test_phase_3_planning.py -x -q`

  Expected: PASS.

- [ ] **Step 6: Commit Phase 3 backend planning**

  Run: `git add backend/app backend/tests/test_phase_3_planning.py && git commit -m "feat: add phase 3 volume arcs and plan versions"`

## Task 6: Extend chapter planning from “next chapter” to long-form structure

**Files:**
- Modify: `backend/app/models/writing.py`
- Modify: `backend/app/repositories/writing_repo.py`
- Modify: `backend/app/services/writing_service.py`
- Modify: `backend/app/api/writing.py`
- Modify: `backend/app/ai/writer.py`
- Modify: `backend/app/schemas/writing.py`
- Test: `backend/tests/test_phase_1_writing.py`
- Test: `backend/tests/test_phase_3_planning.py`

**Interfaces:**
- Adds list/get/update APIs for chapter plans and supports generating a bounded list of chapter outlines for one active volume arc.
- Extends chapter-plan generation input with active blueprint version, active volume arc, existing chapter summaries, character arcs, and foreshadowing tasks.
- Keeps `POST /chapter-plans/next/generate` as a compatibility endpoint that delegates to the new planning service.

- [ ] **Step 1: Write failing multi-chapter and snapshot tests**

  Assert that a generated chapter plan records its `blueprint_id`, `volume_arc_id`, `version`, `status`, `emotional_effect`, `target_word_count`, `foreshadowing_tasks`, and `acceptance_criteria`. Assert that a writing run’s `input_snapshot` contains the exact active plan and volume-arc versions used at generation time.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `.venv/bin/python -m pytest tests/test_phase_1_writing.py tests/test_phase_3_planning.py -x -q`

  Expected: failures because current chapter plans only store arbitrary JSON and writing runs do not retain planning-version snapshots.

- [ ] **Step 3: Implement version-aware chapter planning**

  Add the foreign-key/version fields, update the generator prompt and fake generator, and persist an immutable input snapshot when creating a writing run. Do not mutate historical plans when a later plan is activated.

- [ ] **Step 4: Add chapter-plan APIs and ownership checks**

  Implement list/get endpoints, active/archived filtering, and explicit plan selection when generating a brief. Reject plans from another novel and reject archived plans for new writing runs.

- [ ] **Step 5: Run the focused tests and commit**

  Run: `.venv/bin/python -m pytest tests/test_phase_1_writing.py tests/test_phase_3_planning.py -x -q`

  Run: `git add backend/app backend/tests && git commit -m "feat: make chapter planning version-aware"`

## Task 7: Add Phase 3 planning workspace UI

**Files:**
- Create: `frontend/src/api/planning.ts`
- Create: `frontend/src/stores/planning.ts`
- Create: `frontend/src/views/novels/PlanningView.vue`
- Create: `frontend/src/components/planning/VolumeArcList.vue`
- Create: `frontend/src/components/planning/PlanVersionTimeline.vue`
- Modify: `frontend/src/components/novels/NovelWorkspaceTabs.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/novels/WritingWorkspaceView.vue`
- Test: `frontend/src/__tests__/PlanningView.spec.ts`

**Interfaces:**
- Produces a planning page showing active blueprint, volume arcs, chapter outline list, version history, current chapter position, unresolved review issues, and foreshadowing risks.
- The UI must allow creating/editing/activating a volume arc and creating a new plan version with change reason and impact scope.

- [ ] **Step 1: Write failing component/store tests**

  Test loading the planning dashboard, rendering active and archived versions, creating a volume arc, and refusing activation when the API returns an ownership or archived-version error.

- [ ] **Step 2: Run the focused frontend tests and verify failure**

  Run: `npm run test:unit -- src/__tests__/PlanningView.spec.ts`

  Expected: module or route failures because the planning page and store do not exist.

- [ ] **Step 3: Implement API and Pinia store**

  Follow the existing `src/api/writing.ts` and `src/stores/writing.ts` patterns. Keep the active plan and version state normalized so activating one item updates the timeline without mutating archived objects.

- [ ] **Step 4: Implement the planning page and navigation**

  Add a planning tab and route. Link the planning page to the writing workspace so the author can select a chapter plan, inspect its source volume/version, and continue to task-book generation.

- [ ] **Step 5: Run frontend tests and type checks**

  Run: `npm run test:unit -- src/__tests__/PlanningView.spec.ts`

  Run: `npm run type-check`

- [ ] **Step 6: Commit Phase 3 frontend planning**

  Run: `git add frontend/src && git commit -m "feat: add phase 3 planning workspace"`

## Task 8: Integrate both tracks and verify the second-edition minimum loop

**Files:**
- Modify: `backend/tests/test_phase_2_quality_gate.py`
- Modify: `backend/tests/test_phase_1_writing_integration.py`
- Create: `backend/tests/test_v2_end_to_end.py`
- Modify: `frontend/src/__tests__/WritingEditor.spec.ts`
- Modify: `frontend/e2e/vue.spec.ts`
- Modify: `docs/novel-agent系统需求文档第二版.md`
- Modify: `AGENTS.md` only if commands or architecture actually change

**Interfaces:**
- Verifies the complete path: author idea → blueprint activation → volume/plan version selection → chapter brief → context package → draft → real quality gate → repair or accept → pending memory → author confirmation → next planning context.

- [ ] **Step 1: Write the end-to-end acceptance test**

  Use fake writing, quality, and extraction providers. Assert that the accepted chapter contains the draft, the writing run retains its plan snapshot, the quality issue is traceable, pending repairs can be resolved, and the next context package includes confirmed memory data.

- [ ] **Step 2: Run the full backend suite and fix integration failures**

  Run: `.venv/bin/python -m pytest tests/ -x -q`

  Expected: all backend tests pass without calling DeepSeek.

- [ ] **Step 3: Run frontend validation**

  Run: `npm run type-check`

  Run: `npm run test:unit`

  Run: `npm run build`

- [ ] **Step 4: Update project documentation**

  Update the second-edition document’s current baseline and route notes only after the end-to-end test passes. Record that Phase 2 and Phase 3 are implemented, and list any intentionally deferred vector retrieval or batch-writing work.

- [ ] **Step 5: Commit the integrated verification**

  Run: `git add backend/tests frontend/src docs/novel-agent系统需求文档第二版.md AGENTS.md && git commit -m "test: verify phase 2 and phase 3 writing loop"`

## Parallel execution order

1. Task 1 is shared and must land first.
2. After Task 1, Tasks 2–4 form the Phase 2 track; Tasks 5–7 form the Phase 3 track. They may be developed in parallel only if they do not edit the same file at the same time.
3. If two tasks need `backend/app/models/writing.py`, `backend/app/api/writing.py`, or the shared migration, finish the contract change first and rebase the second task on it.
4. Task 8 starts only after both tracks pass their focused tests.

## Spec coverage review

- The second-edition Phase 2 requirements for task completion, character, continuity, foreshadowing, length, density, world, style, and readability are covered by Task 2.
- The second-edition Phase 3 requirements for plan versions, volume arcs, mainline progression, character arcs, and foreshadowing lifecycle are covered by Tasks 5–6.
- The author-confirmation rule is preserved by Tasks 3–4 and the end-to-end test in Task 8.
- DraftVersion, local rewrite diffing, and advanced retrieval remain outside this plan; they belong to the documented Phase 4 and Phase 5 work.

