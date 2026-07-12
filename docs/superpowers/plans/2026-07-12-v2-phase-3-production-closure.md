# Phase 3 Production Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Phase 3 动态剧情规划从“确定性测试通过”收尾为真实 DeepSeek 可用、前端可操作、决策与局部修订状态完整且可验收的生产闭环。

**Architecture:** 先修复 `PlotPlanningService` 的真实 AI 入口和结构化协议，再补齐决策选择/候选修订的事务状态，随后把剧情计划 ID 贯穿现有任务书、上下文和写作运行 API，最后完成工作台 UI 和全量验收。测试生成器继续通过构造函数注入，生产路径绝不回退到 Fake。

**Tech Stack:** FastAPI, Python 3.12, async SQLAlchemy, Alembic, Pydantic v2, DeepSeek via LangChain, Vue 3, TypeScript, Pinia, Vitest, Vite.

## Global Constraints

- Backend commands run from `backend/`; frontend commands run from `frontend/`.
- All API routes remain under `/api/v1/novels/{novel_id}/` and use the existing unified `ApiResponse` wrapper.
- `Chapter.status == "locked"` is immutable; no plan, revision, accept, update, delete, or publish path may change locked content.
- `PlotPlanningService` defaults to `DeepSeekWritingGenerator`; Fake generators are test-only constructor injections.
- `PlotPlanOutput`, `DraftGenerationOutput`, `DraftReviewOutput`, and `LocalRevisionOutput` must be Pydantic-validated before database writes.
- Existing Phase 1/2 blueprints, chapter plans, briefs, quality gates, repairs, and memory extraction remain available and must not regress.
- Frontend Vue and Element Plus APIs are auto-imported; do not add manual imports for globally configured Vue/Element Plus symbols.
- Frontend formatting remains `semi: false`, `singleQuote: true`, `printWidth: 100`.
- Every task ends with a focused verification command and an intentional commit.

---

### Task 1: Use the real planning generator and normalize structured plan output

**Files:**
- Modify: `backend/app/services/plot_planning_service.py:12-43,140-202`
- Test: `backend/tests/test_phase_3_dynamic_plot_planning.py`

**Interfaces:**
- Consumes: `BaseWritingGenerator`, `FakePhase3WritingGenerator`, `DeepSeekWritingGenerator`, and `PlotPlanOutput`.
- Produces: `PlotPlanningService._normalize_plot_plan_output(output: dict | PlotPlanOutput) -> dict` and a production default of `DeepSeekWritingGenerator()`.

- [ ] **Step 1: Write failing tests for the production default and Pydantic normalization**

Add tests near the existing Phase 3 protocol tests:

```python
def test_plot_plan_output_normalizes_to_dict():
    output = PlotPlanOutput(
        starting_state="主角抵达边城",
        stage_goal="查清旧案",
        core_conflict="调查触动守城势力",
        key_turns=[{"order": 1, "event": "发现线索", "required": True}],
        progression=[{"order": 1, "chapter_position": 1, "purpose": "推进调查", "scenes": ["牢狱"]}],
        completion_criteria=["找到关键证人"],
    )
    assert PlotPlanningService._normalize_plot_plan_output(output)["core_conflict"] == "调查触动守城势力"


def test_plot_planning_service_defaults_to_deepseek(db):
    service = PlotPlanningService(db=db, user_id=1, novel_id=1)
    assert isinstance(service.generator, DeepSeekWritingGenerator)
```

Import `PlotPlanOutput`, `DeepSeekWritingGenerator`, and `PlotPlanningService` using the existing project imports.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py::test_plot_plan_output_normalizes_to_dict tests/test_phase_3_dynamic_plot_planning.py::test_plot_planning_service_defaults_to_deepseek -q
```

Expected: failure because the service currently defaults to `FakePhase3WritingGenerator` and has no normalization helper.

- [ ] **Step 3: Implement the smallest production-generator and normalization change**

In `plot_planning_service.py`:

```python
from pydantic import BaseModel
from app.ai.plot_planning import ConflictOutput, LocalRevisionOutput, PlotPlanOutput
from app.ai.writer import BaseWritingGenerator, DeepSeekWritingGenerator


class PlotPlanningService:
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

    @staticmethod
    def _normalize_plot_plan_output(output: dict | PlotPlanOutput) -> dict:
        if isinstance(output, BaseModel):
            return output.model_dump()
        if isinstance(output, dict):
            return output
        raise BadRequest("生成器返回无效剧情计划")
```

In `generate_plan()`, replace the `isinstance(plan_output, dict)` branch with the helper and persist only the normalized dictionary. Do not add any Fake fallback.

- [ ] **Step 4: Run the focused tests and the existing Phase 3 suite**

```bash
cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py::test_plot_plan_output_normalizes_to_dict tests/test_phase_3_dynamic_plot_planning.py::test_plot_planning_service_defaults_to_deepseek -q
cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py -q
```

Expected: the focused tests and all existing deterministic Phase 3 tests pass. Tests that need a Fake generator must continue passing an explicit `generator=` argument.

- [ ] **Step 5: Commit the production generator boundary**

```bash
git add backend/app/services/plot_planning_service.py backend/tests/test_phase_3_dynamic_plot_planning.py
git commit -m "fix: use real generator for phase 3 planning"
```

### Task 2: Persist decision choices and make decision payloads schema-safe

**Files:**
- Create: `backend/alembic/versions/e2f3a4b5c6d7_phase_3_decision_choices.py`
- Modify: `backend/app/models/plot_planning.py:74-92`
- Modify: `backend/app/schemas/plot_planning.py:90-108`
- Modify: `backend/app/services/plot_planning_service.py:229-268,285-338`
- Test: `backend/tests/test_phase_3_dynamic_plot_planning.py`

**Interfaces:**
- Consumes: `PlanningDecision`, `ConflictOutput`, and `ChooseDecisionRequest`.
- Produces: `PlanningDecision.selected_option_index: int | None`, `PlanningDecision.custom_intent: str | None`, and schema-safe `evidence_json`.

- [ ] **Step 1: Write failing tests for evidence normalization and author-choice persistence**

Add:

```python
@pytest.mark.asyncio
async def test_conflict_evidence_is_schema_safe_and_choice_is_persisted(db):
    # Build the existing foundation, plot unit, active plan, and blocked run fixtures.
    conflict = conflict_output().model_copy(update={"evidence": [{"chapter_id": 1, "fact": "锁定事实"}]})
    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=FakePhase3WritingGenerator())
    decision = await service.create_decision_from_conflict(conflict, "during_generation", run_id=1)
    assert decision.evidence_json == {"items": [{"chapter_id": 1, "fact": "锁定事实"}]}

    await service.choose_decision(decision.id, custom_intent="保留事实并补充因果")
    refreshed = await service.get_decision(decision.id)
    assert refreshed.selected_option_index is None
    assert refreshed.custom_intent == "保留事实并补充因果"
    PlanningDecisionOut.model_validate(refreshed)
```

Add a parallel option-index assertion to the existing decision-selection test:

```python
assert resolved_decision.selected_option_index == 0
assert resolved_decision.custom_intent is None
```

Update the existing `run.planning_blocked` assertion in that test to remain `True` until the candidate is applied; the apply step belongs to Task 3.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py::test_conflict_evidence_is_schema_safe_and_choice_is_persisted -q
```

Expected: failure because the model has no choice columns and non-empty evidence is stored as a list.

- [ ] **Step 3: Add the model fields and migration**

Add to `PlanningDecision`:

```python
selected_option_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
custom_intent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

Create `e2f3a4b5c6d7_phase_3_decision_choices.py` with `down_revision = "d1e2f3a4b5c6"`, adding and dropping these two columns on `planning_decisions`. Do not alter or recreate existing Phase 3 tables.

- [ ] **Step 4: Normalize evidence and persist the selected author direction**

In `create_decision_from_conflict()` replace the evidence value with:

```python
"evidence_json": {"items": conflict.evidence or []},
```

In `choose_decision()` after the AI revision succeeds and before commit:

```python
decision.selected_option_index = option_index
decision.custom_intent = custom_intent if option_index is None else None
decision.updated_at = datetime.datetime.now()
```

Expose both fields through `PlanningDecisionOut` and add them to `frontend/src/types/plotPlanning.ts` in Task 4.

- [ ] **Step 5: Verify migration and focused tests**

```bash
cd backend && .venv/bin/python -m alembic upgrade head
cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py::test_conflict_evidence_is_schema_safe_and_choice_is_persisted tests/test_phase_3_dynamic_plot_planning.py::test_choose_decision_preserves_unaffected_text_and_creates_new_plan -q
```

Expected: migration succeeds and both tests pass.

- [ ] **Step 6: Commit the decision schema change**

```bash
git add backend/alembic/versions/e2f3a4b5c6d7_phase_3_decision_choices.py backend/app/models/plot_planning.py backend/app/schemas/plot_planning.py backend/app/services/plot_planning_service.py backend/tests/test_phase_3_dynamic_plot_planning.py
git commit -m "feat: persist phase 3 decision choices"
```

### Task 3: Make review conflicts and candidate revisions transactional

**Files:**
- Modify: `backend/app/services/plot_planning_service.py:229-386`
- Modify: `backend/app/services/writing_service.py:530-610`
- Modify: `backend/app/repositories/plot_planning_repo.py:150-177`
- Modify: `backend/app/api/planning.py:167-185`
- Test: `backend/tests/test_phase_3_dynamic_plot_planning.py`

**Interfaces:**
- Consumes: `PlanningDecision`, `WritingRun`, `DraftRevision`, and `LocalRevisionOutput`.
- Produces: `PlotPlanningService.apply_draft_revision(revision_id: int) -> DraftRevision` and `PUT /api/v1/novels/{novel_id}/draft-revisions/{revision_id}/apply`.

- [ ] **Step 1: Write failing tests for review blocking, candidate application, stale decisions, and rollback**

Add tests with the existing fixtures:

```python
@pytest.mark.asyncio
async def test_review_conflict_sets_planning_blocked(db):
    # Build a completed run with a Phase 3 context snapshot and a fake review conflict.
    result = await service.review_writing_run(run.id)
    assert result["decision"] is not None
    refreshed = await db.get(WritingRun, run.id)
    assert refreshed.planning_blocked is True


@pytest.mark.asyncio
async def test_choose_decision_keeps_candidate_unapplied_until_apply(db):
    decision, _, revision, run = await service.choose_decision(decision.id, option_index=0)
    assert revision.status == "candidate"
    assert run.draft_content == "开头不变。旧冲突场景。结尾不变。"
    applied = await service.apply_draft_revision(revision.id)
    assert applied.status == "applied"
    assert run.draft_content == applied.candidate_content


@pytest.mark.asyncio
async def test_apply_candidate_marks_sibling_candidates_superseded(db):
    # Create two candidates for one run, apply the newer one, and assert only it is applied.
    await service.apply_draft_revision(newer.id)
    assert older.status == "superseded"
    assert newer.status == "applied"


@pytest.mark.asyncio
async def test_stale_decision_cannot_apply_after_foundation_update(db):
    await foundation_service.update_foundation({"stage_goal": "新目标"}, "author changed goal")
    with pytest.raises(BadRequest, match="过期"):
        await service.choose_decision(decision.id, option_index=0)
```

Update the existing generator-failure test to assert the old plan remains active, the decision remains pending, no candidate revision is created, and `run.draft_content` is unchanged.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py::test_review_conflict_sets_planning_blocked tests/test_phase_3_dynamic_plot_planning.py::test_choose_decision_keeps_candidate_unapplied_until_apply tests/test_phase_3_dynamic_plot_planning.py::test_stale_decision_cannot_apply_after_foundation_update -q
```

Expected: failure because review does not set the run block and there is no candidate-apply service.

- [ ] **Step 3: Make conflict creation ownership-safe and review conflicts blocking**

In `create_decision_from_conflict()` require an existing run with `run.novel_id == self.novel_id`; otherwise raise `NotFound`. When `review_writing_run()` creates a narrative decision, update the run so an unaccepted run becomes `decision_required`, while an accepted run remains `accepted` with `planning_blocked=True`.

Do not change the Phase 2 `ReviewIssue` path for style, length, or expression issues.

- [ ] **Step 4: Make candidate selection atomic and keep candidate content unapplied**

In `choose_decision()`:

1. Load the latest draft revision with repository ordering `created_at.desc()`.
2. Confirm the linked plan is still the current decision plan and has not been superseded or made stale.
3. Call `revise_draft()` before any persistent state mutation.
4. Wrap plan archival, plan creation, candidate creation, and decision updates in `async with self.db.begin_nested():`.
5. Keep `run.draft_content` unchanged and leave the run blocked until `apply_draft_revision()`.
6. Set the decision choice fields from Task 2.
7. Commit once after the savepoint succeeds.

If any post-AI write fails, call `rollback()` and re-raise the existing application error so the request session cannot reuse dirty state.

- [ ] **Step 5: Implement candidate application**

Add repository ordering:

```python
async def list_draft_revisions_by_run(self, writing_run_id: int) -> list[DraftRevision]:
    result = await self.db.execute(
        select(DraftRevision)
        .where(DraftRevision.writing_run_id == writing_run_id)
        .order_by(DraftRevision.created_at.desc())
    )
    return list(result.scalars().all())
```

Implement `apply_draft_revision()` with these checks:

- The revision belongs to the current novel.
- The revision is `candidate`.
- The linked run belongs to the current novel and has draft content.
- A target chapter is either absent or not `locked`.
- No newer candidate exists for the same run.

On success, mark same-run candidates other than the selected revision as `superseded`, set the selected revision to `applied`, write its `candidate_content` to `run.draft_content`, set `run.status = "completed"` when it was `decision_required`, set `run.planning_blocked = False`, and commit.

- [ ] **Step 6: Add the apply route and response**

Add to `backend/app/api/planning.py`:

```python
@router.put("/draft-revisions/{revision_id}/apply")
async def apply_draft_revision(
    novel_id: int,
    revision_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _get_service(db, current_user, novel_id)
    revision = await svc.apply_draft_revision(revision_id)
    return ApiResponse.success(data=DraftRevisionOut.model_validate(revision).model_dump())
```

- [ ] **Step 7: Run backend regression tests and commit**

```bash
cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py -q
cd backend && .venv/bin/python -m pytest tests/test_phase_2_quality_gate.py -q
git add backend/app/services/plot_planning_service.py backend/app/services/writing_service.py backend/app/repositories/plot_planning_repo.py backend/app/api/planning.py backend/tests/test_phase_3_dynamic_plot_planning.py
git commit -m "feat: complete phase 3 decision revision transaction"
```

Expected: all deterministic Phase 3 tests pass and Phase 2 quality-gate tests have no new failures.

### Task 4: Complete frontend API and store contracts

**Files:**
- Modify: `frontend/src/types/plotPlanning.ts:75-130`
- Modify: `frontend/src/types/writing.ts:80-104`
- Modify: `frontend/src/api/planning.ts:1-52`
- Modify: `frontend/src/api/writing.ts:26-84`
- Modify: `frontend/src/stores/plotPlanning.ts:1-120`
- Modify: `frontend/src/stores/writing.ts:60-100`
- Test: `frontend/src/__tests__/PlotPlanning.spec.ts`

**Interfaces:**
- Consumes: backend routes for plan revisions, writing brief/context/run creation, decisions, review, candidate application, and publish.
- Produces: typed Phase 3 requests and store actions that preserve local candidate state on API failure.

- [ ] **Step 1: Add failing API/store contract tests**

Mock the axios client and assert exact payloads:

```ts
it('sends the selected plot plan through brief, context, and run creation', async () => {
  await writingApi.generateChapterBrief(1, 10, 20, '本章保护证人')
  expect(client.post).toHaveBeenCalledWith('/novels/1/chapter-briefs/generate', {
    chapter_plan_id: 10,
    plot_plan_revision_id: 20,
    author_input: '本章保护证人',
  })
})

it('applies a draft revision through the planning API', async () => {
  await planningApi.applyDraftRevision(1, 30)
  expect(client.put).toHaveBeenCalledWith('/novels/1/draft-revisions/30/apply')
})
```

Add a store test that rejects an API error without replacing `currentDraftRevision`.

- [ ] **Step 2: Run the focused frontend tests and verify RED**

```bash
cd frontend && npm run test:unit -- src/__tests__/PlotPlanning.spec.ts
```

Expected: failure because current API signatures do not accept the Phase 3 parameters and no apply action exists.

- [ ] **Step 3: Update frontend literal types and API signatures**

Use these signatures:

```ts
export function generateChapterBrief(
  novelId: number,
  chapterPlanId: number,
  plotPlanRevisionId?: number,
  authorInput?: string,
): Promise<ChapterBrief>

export function generateContextPackage(
  novelId: number,
  chapterBriefId: number,
  plotPlanRevisionId?: number,
  authorInput?: string,
): Promise<ContextPackage>

export function createWritingRun(
  novelId: number,
  chapterBriefId: number,
  plotPlanRevisionId?: number,
  authorInput?: string,
): Promise<WritingRun>

export function applyDraftRevision(novelId: number, revisionId: number): Promise<DraftRevision>
```

Add `selected_option_index` and `custom_intent` to `PlanningDecision`, and add a `DraftRevisionApplyResponse` alias only if the API response needs a distinct type; otherwise reuse `DraftRevision`.

- [ ] **Step 4: Update Pinia stores with selected-unit and Phase 3 parameters**

Add to `plotPlanning.ts`:

```ts
const selectedPlotUnit = ref<PlotUnit | null>(null)
const planRevisions = ref<PlotPlanRevision[]>([])

async function selectPlotUnit(novelId: number, unit: PlotUnit) {
  selectedPlotUnit.value = unit
  planRevisions.value = await api.listPlotPlans(novelId, unit.id)
  activePlan.value = planRevisions.value.find(plan => plan.status === 'active') || null
}
```

Expose `selectedPlotUnit`, `planRevisions`, and `selectPlotUnit`. Update writing-store methods to accept and forward `plotPlanRevisionId` and `authorInput` without mutating old Phase 1/2 callers.

- [ ] **Step 5: Run type-check and focused tests**

```bash
cd frontend && npm run test:unit -- src/__tests__/PlotPlanning.spec.ts
cd frontend && npm run type-check
```

Expected: focused tests and type-check pass.

- [ ] **Step 6: Commit the frontend contracts**

```bash
git add frontend/src/types/plotPlanning.ts frontend/src/types/writing.ts frontend/src/api/planning.ts frontend/src/api/writing.ts frontend/src/stores/plotPlanning.ts frontend/src/stores/writing.ts frontend/src/__tests__/PlotPlanning.spec.ts
git commit -m "feat: wire phase 3 frontend API contracts"
```

### Task 5: Render the Phase 3 workspace and complete decision/revision UI

**Files:**
- Create: `frontend/src/components/writing/AuthorFoundationPanel.vue`
- Modify: `frontend/src/components/writing/PlotUnitPanel.vue:1-107`
- Modify: `frontend/src/components/writing/DecisionCard.vue:1-85`
- Modify: `frontend/src/components/writing/DraftRevisionDiff.vue:1-64`
- Modify: `frontend/src/views/novels/WritingWorkspaceView.vue:1-395`
- Test: `frontend/src/__tests__/PlotPlanning.spec.ts`
- Test: `frontend/src/__tests__/WritingEditor.spec.ts`

**Interfaces:**
- Consumes: Task 4 store actions and typed API functions.
- Produces: a user-operable Phase 3 workflow with no placeholder success actions.

- [ ] **Step 1: Replace placeholder component tests with behavioral tests**

Replace the existing `PlotUnitPanel` placeholder test with:

```ts
it('selects a plot unit and emits plan actions', async () => {
  const wrapper = mount(PlotUnitPanel, {
    props: { plotUnits: [plotUnitFixture], activePlan: planFixture, loading: false },
    global: { stubs: globalStubs },
  })
  await wrapper.find('.plot-unit-panel__item-header').trigger('click')
  expect(wrapper.emitted('selectUnit')?.[0]).toEqual([plotUnitFixture])
})
```

Add tests that `DecisionCard` emits `{ decisionId, optionIndex }`, the custom-intent action emits the correct decision ID, and `DraftRevisionDiff` emits only `apply` with the candidate revision ID.

- [ ] **Step 2: Run focused component tests and verify RED**

```bash
cd frontend && npm run test:unit -- src/__tests__/PlotPlanning.spec.ts src/__tests__/WritingEditor.spec.ts
```

Expected: failures because the current components do not carry decision IDs, the plot-unit selection state is never assigned, and the placeholder actions are still present.

- [ ] **Step 3: Create the author-foundation panel**

Create `AuthorFoundationPanel.vue` with typed props:

```ts
defineProps<{
  foundation: AuthorFoundation | null
  loading: boolean
}>()

defineEmits<{
  save: [data: AuthorFoundationUpdate]
}>()
```

Render outline, current intent, stage goal, and a save button. Do not expose revision history editing in this task; the store/API already preserve it.

- [ ] **Step 4: Make PlotUnitPanel selection and plan confirmation functional**

Set `selectedUnitId.value = unit.id` in `selectUnit`, emit `selectUnit`, and show the selected unit’s active/draft plan state. Keep the existing create and generate events, but do not clear the input until the parent confirms the API succeeded.

- [ ] **Step 5: Make decision cards and candidate diff server-backed**

In `DecisionCard.vue`, emit:

```ts
emit('choose', { decisionId: props.decision.id, optionIndex: index })
```

and for custom intent:

```ts
emit('choose', { decisionId: props.decision.id, customIntent: customIntent.value.trim() })
```

In `DraftRevisionDiff.vue`, remove the no-op `replace` event and expose one `apply` event. Disable the button unless `revision.status === 'candidate'` and the parent has selected the candidate.

- [ ] **Step 6: Wire WritingWorkspaceView to the Phase 3 sequence**

Render `AuthorFoundationPanel` and `PlotUnitPanel` in the workspace. On plot-unit selection call `ppStore.selectPlotUnit()`. Change brief, context, and run handlers to pass `ppStore.activePlan?.id` and the current author input. Disable Phase 3 writing when no active plan exists.

Use these stable test hooks in the rendered controls:

```html
<el-button data-testid="save-foundation">保存作者资料</el-button>
<el-button data-testid="generate-plot-plan">生成计划</el-button>
<el-button data-testid="confirm-plot-plan">确认计划</el-button>
```

Update decision handling to use the emitted `decisionId`, call the store, and show the returned candidate. Update `handleApplyDraft()` to call `planningApi.applyDraftRevision()` and refresh the writing run; remove the success-only placeholder implementation.

- [ ] **Step 7: Verify locked editor behavior and UI tests**

```bash
cd frontend && npm run test:unit -- src/__tests__/PlotPlanning.spec.ts src/__tests__/WritingEditor.spec.ts
cd frontend && npm run type-check
```

Expected: all focused tests pass; locked editor remains read-only and has no publish/save controls.

- [ ] **Step 8: Commit the Phase 3 workspace**

```bash
git add frontend/src/components/writing/AuthorFoundationPanel.vue frontend/src/components/writing/PlotUnitPanel.vue frontend/src/components/writing/DecisionCard.vue frontend/src/components/writing/DraftRevisionDiff.vue frontend/src/views/novels/WritingWorkspaceView.vue frontend/src/__tests__/PlotPlanning.spec.ts frontend/src/__tests__/WritingEditor.spec.ts
git commit -m "feat: complete phase 3 writing workspace"
```

### Task 6: Add deterministic API E2E coverage for the full Phase 3 lifecycle

**Files:**
- Modify: `backend/tests/test_phase_3_dynamic_plot_planning.py:958-1120`
- Create: `frontend/src/__tests__/WritingWorkspacePhase3.spec.ts`
- Modify: `docs/superpowers/plans/2026-07-10-v2-phase-3-dynamic-plot-planning-acceptance.md`

**Interfaces:**
- Consumes: all backend and frontend contracts from Tasks 1–5.
- Produces: a deterministic full-flow acceptance test and an updated acceptance record that distinguishes deterministic and real-AI results.

- [ ] **Step 1: Extend the backend E2E scenario to apply the candidate through the API**

Change the existing scenario after decision selection to assert:

```python
assert resolved_run.draft_content == original_conflicting_content
apply_response = await client.put(
    f"/api/v1/novels/{novel_id}/draft-revisions/{draft_revision.id}/apply",
    headers=headers,
)
assert apply_response.status_code == 200
assert apply_response.json()["data"]["status"] == "applied"
```

Then accept the run, publish the chapter, reject a locked update, and build the next context package to assert the locked chapter ID is present.

- [ ] **Step 2: Add cross-user and pending-decision API checks**

Assert that a second user receives 404 for the decision, candidate-apply endpoint, and plot-plan endpoint. Assert that publishing while a pending decision exists returns 400 and does not change chapter status.

- [ ] **Step 3: Add frontend workspace integration tests**

Mount the workspace with mocked API functions and assert the sequence:

```ts
await wrapper.find('[data-testid="save-foundation"]').trigger('click')
await wrapper.find('[data-testid="generate-plot-plan"]').trigger('click')
await wrapper.find('[data-testid="confirm-plot-plan"]').trigger('click')
expect(writingApi.createWritingRun).toHaveBeenCalledWith(1, 10, 20, expect.any(String))
```

Add a decision fixture with two pending cards and assert clicking the second card calls `chooseDecision()` with the second ID.

- [ ] **Step 4: Run deterministic backend and frontend acceptance tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py -q
cd frontend && npm run test:unit -- src/__tests__/WritingWorkspacePhase3.spec.ts
```

Expected: all deterministic Phase 3 tests and the workspace flow pass without a DeepSeek call.

- [ ] **Step 5: Update the acceptance record with accurate scope**

Record the new migration revision, deterministic test count, candidate-apply behavior, frontend tests, and any real-AI test skip. Remove any statement that calls lint or unrelated live-AI failures “unrelated” without recording the exact command and cause.

- [ ] **Step 6: Commit deterministic acceptance coverage**

```bash
git add backend/tests/test_phase_3_dynamic_plot_planning.py frontend/src/__tests__/WritingWorkspacePhase3.spec.ts docs/superpowers/plans/2026-07-10-v2-phase-3-dynamic-plot-planning-acceptance.md
git commit -m "test: add phase 3 production closure acceptance"
```

### Task 7: Run migration, real-AI, frontend, and regression verification

**Files:**
- Modify only if verification exposes a defect: `backend/alembic/versions/e2f3a4b5c6d7_phase_3_decision_choices.py`
- Modify only if verification exposes a defect: `docs/superpowers/plans/2026-07-10-v2-phase-3-dynamic-plot-planning-acceptance.md`

**Interfaces:**
- Consumes: the complete implementation from Tasks 1–6.
- Produces: verified Phase 3 closure with exact command output and known limitations documented.

- [ ] **Step 1: Verify migration chain**

Run from `backend/`:

```bash
.venv/bin/python -m alembic heads
.venv/bin/python -m alembic upgrade d1e2f3a4b5c6
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic downgrade d1e2f3a4b5c6
.venv/bin/python -m alembic upgrade head
```

Expected: one head, clean upgrade/downgrade/re-upgrade, and no loss of Phase 2 tables.

- [ ] **Step 2: Run deterministic backend regression**

```bash
cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py tests/test_phase_2_quality_gate.py -q
```

Expected: all deterministic Phase 3 and Phase 2 tests pass. Live DeepSeek tests must not be counted in this result.

- [ ] **Step 3: Run real DeepSeek integration explicitly**

With a configured key:

```bash
cd backend && DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning_integration.py -q
```

Without a configured key, run the same command and record the explicit skip reason. The production planning service must never be changed to Fake merely to make this command pass.

- [ ] **Step 4: Run all frontend checks**

```bash
cd frontend && npm run test:unit
cd frontend && npm run type-check
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: all commands exit 0. If lint finds an existing test-only rule violation, fix the test rather than weakening the rule.

- [ ] **Step 5: Inspect the final diff and locked safety paths**

Run:

```bash
git diff --check
git diff --stat HEAD~7..HEAD
git status --short
rg -n "status == \\"locked\\"|status = \\"locked\\"|chapter\\.content =|draft_content =" backend/app frontend/src
```

Confirm that every `Chapter.content` assignment is guarded, `DraftRevision` application cannot target a locked chapter, and no production service imports or defaults to `FakePhase3WritingGenerator`.

- [ ] **Step 6: Mark the acceptance record complete only after evidence is present**

Update the acceptance record with actual counts and command results. If real AI is skipped, label it skipped; do not call the full Phase 3 implementation complete without the documented real-AI result or explicit environment limitation.

- [ ] **Step 7: Commit the final verification record**

```bash
git add docs/superpowers/plans/2026-07-10-v2-phase-3-dynamic-plot-planning-acceptance.md
git commit -m "docs: record phase 3 closure verification"
```
