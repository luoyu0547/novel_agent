# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Reference

See `AGENTS.md` for commands (build, test, lint, run), architecture overview, and key data enums. This file supplements with patterns and subsystems that require reading multiple files to understand.

## Backend layer architecture

```
api/ (routes, thin) → services/ (business logic) → repositories/ (DB queries) → models/ (SQLAlchemy ORM)
```

- Routes delegate to services immediately — no business logic in route handlers.
- Services receive `db: AsyncSession`, `user_id`, `novel_id` in `__init__` and own all resource-access checks via `_ensure_owned_novel()`.
- Repositories are plain classes that receive `db` in `__init__` and return ORM model instances or lists.
- All endpoint responses use `ApiResponse.success()` / `ApiResponse.error()` from `app/core/response.py`.

## Testing patterns

### Backend tests
- Organized by phase: `test_phase_1_*.py`, `test_phase_2_*.py`, `test_phase_3_*.py`.
- `conftest.py` sets `APP_ENV=test`, uses SQLite, and provides autouse `reset_database` (drop+recreate all tables before each test), `client` (httpx AsyncClient), and `db` (raw session) fixtures.
- **Dependency injection for testing**: Services accept optional constructor args (`generator=`, `gate_agent=`, `extraction_service=`) that default to real DeepSeek implementations but accept fakes. Tests inject `FakeWritingGenerator`, `FakeQualityGateAgent`, `FakePhase3WritingGenerator` to avoid real API calls.
- `FakePhase3WritingGenerator` accepts pre-built outputs (`plot_plan`, `draft_result`, `review`, `revision`) for deterministic per-test control.
- Run single test: `.venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py::test_function_name -x -q`

### Frontend tests
- Vitest with jsdom for unit tests, Playwright for e2e.
- Test files live in `src/__tests__/`, co-located by feature (e.g., `WritingWorkspacePhase3.spec.ts`).
- Stores can be tested with `@pinia/testing` (`createTestingPinia`).

## Phase 3: Dynamic plot planning module

The Phase 3 system adds decision-driven narrative planning on top of the Phase 1/2 writing pipeline. Key models in `app/models/plot_planning.py`:

```
AuthorFoundation → (versioned via AuthorFoundationRevision)
    ↓
PlotUnit (scoped to foundation_revision, spans N chapters)
    ↓ generate_plan()
PlotPlanRevision (versioned, status: draft/active/stale/superseded/blocked)
    ↓ create_writing_run()
WritingRun → AI generates draft → may hit conflicts → PlanningDecision (status: pending/resolved/superseded)
    ↓ choose_decision()
DraftRevision (candidate/applied/superseded)
```

**Key flow:**
1. Author sets foundation (outline, intent, constraints) → creates PlotUnit.
2. `generate_plan()` calls `DeepSeekWritingGenerator.generate_plot_plan()` → creates PlotPlanRevision.
3. `confirm_plan()` promotes revision to `active`.
4. `create_writing_run()` with `plot_plan_revision_id` uses structured generation (`generate_draft_result()`):
   - `draft_ready` → normal quality gate flow.
   - `decision_required` → creates `PlanningDecision` + `DraftRevision(candidate)`, sets run status to `decision_required`.
   - `unsafe_planning` → sets run status to `failed`.
5. `choose_decision()` resolves a decision, calls AI to revise draft, creates new DraftRevision + optionally new PlotPlanRevision.
6. `apply_draft_revision()` applies candidate content back to the WritingRun.

**Service**: `PlotPlanningService` (`app/services/plot_planning_service.py`), endpoints in `app/api/planning.py`.

## Quality gate auto-fix loop

Inside `WritingService.create_writing_run()`, after draft generation:

1. Pre-gate check: `_check_gate()` validates word count and outline detection. If count < `min_words`, re-generates once with `expansion_hint`.
2. Main loop (`max_iterations=3`): `QualityGateService.run()` runs 7 agent types (`task_completion`, `style`, `character`, `continuity`, `world`, `foreshadowing`, `length`). Each returns `CheckResult` with severity `auto_fixable` or `needs_intent`.
3. If `rewrite_needed`: collects RepairLog descriptions as feedback, cleans up stale gate records, re-generates draft, re-runs gate.
4. After loop: final state includes `gated` (any issues), `has_pending_repairs` (needs-intent issues → `PendingRepair` rows).

**Key classes**: `BaseQualityGateAgent` / `DeepSeekQualityGateAgent` in `app/ai/quality_gate.py` (interface) and `app/ai/quality_agents.py` (implementation). `QualityGateService` in `app/services/quality_gate_service.py`.

## Context package

`ContextPackageService.build_for_brief()` in `app/services/context_package_service.py` builds the full AI input snapshot:
- AuthorFoundation + latest revision
- Published canon (locked chapters with full content)
- PlotUnit + PlotPlanRevision
- Characters, world settings, plot facts, foreshadowings
- Style guide, author input, snapshot metadata

Used by `create_writing_run()` when `plot_plan_revision_id` is provided (Phase 3 path).

## AI module structure

```
app/ai/
  agent.py          — factory functions (create_novel_agent, create_novel_deep_agent)
  config.py          — model names (FLASH_MODEL, PRO_MODEL)
  models.py          — NovelAgentState (LangGraph state schema)
  writer.py          — BaseWritingGenerator, DeepSeekWritingGenerator, fakes
  quality_gate.py    — BaseQualityGateAgent, CheckResult, AGENT_TYPES, fakes
  quality_agents.py  — DeepSeekQualityGateAgent (real implementation)
  plot_planning.py   — Pydantic models for structured AI output (PlotPlanOutput,
                       DraftGenerationOutput, DraftReviewOutput, ConflictOutput,
                       LocalRevisionOutput, AIProtocolError)
  router.py          — extraction and AI endpoints
  service.py         — extraction service (DeekSeekExtractionService)
  middleware/         — LangGraph middleware (logging)
  tools/              — LangChain tools (context.py, memory.py)
```

## Frontend store pattern

Pinia stores in `src/stores/` follow a consistent pattern:
- Each store file exports `useXxxStore` with `defineStore`.
- Async actions call API modules from `src/api/` then update state.
- API client (`src/api/client.ts`) auto-attaches JWT token and unwraps `ApiResponse.data`.
- Types in `src/types/` mirror backend Pydantic schemas.

## Database

- Dev: SQLite via `aiosqlite` (tables auto-created on startup via `Base.metadata.create_all`).
- Prod: MySQL via `aiomysql` (managed via Alembic migrations).
- Tests: SQLite with per-test drop+recreate via autouse fixture.
- `DATABASE_URL` format determines driver: `sqlite+aiosqlite:///...` vs `mysql+aiomysql://...`.
- `expire_on_commit=False` on the session factory (required for async lazy loading).

## Error handling

- Exception hierarchy in `app/core/exceptions.py`: `AppException` → `NotFound(404, 40400)`, `Unauthorized(401, 40100)`, `Forbidden(403, 40300)`, `BadRequest(400, 40000)`.
- Handlers in `app/core/handlers.py` catch these and return `ApiResponse.error(code, message)`.
- Services raise these directly; routes don't need try/except.
- Ownership checks raise `NotFound` for both "doesn't exist" and "not yours" to avoid leaking existence info.
