# Novel Agent

## Project structure
- `backend/` — FastAPI (Python 3.12, async SQLAlchemy, SQLite dev / MySQL prod)
- `frontend/` — Vue 3 + TypeScript + Pinia + Vite
- All commands are directory-scoped: backend commands run from `backend/`, frontend from `frontend/`.

## Backend commands (workdir: `backend/`)
```sh
.venv/bin/python -m uvicorn app.main:app --reload   # dev server (port 8000)
.venv/bin/python -m pytest tests/ -x -q              # run all tests
.venv/bin/python -m alembic upgrade head             # run migrations
```
- **Dev auto-creates tables**: `create_app()` startup runs `Base.metadata.create_all` on every boot, so dev needs no manual migration. Alembic migrations are for prod schema management; the two can drift — if you add a model, write a migration too.
- First-time setup: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cp .env.example .env`
- `.env.example` requires `APP_ENV`, `DATABASE_URL`, `SECRET_KEY`, and `DEEPSEEK_API_KEY`.
- Settings auto-loaded by `pydantic_settings.BaseSettings` from `.env` (file at `backend/app/core/config.py`).
- Tests: `conftest.py` sets `APP_ENV=test`, `DATABASE_URL=sqlite+aiosqlite:///test_novel_agent.db`, and `SECRET_KEY=test-secret-key`; autouse fixture drops + recreates all tables around each test.
- Run single test: `.venv/bin/python -m pytest tests/test_phase_1_manual_memory.py::test_character_profile_crud -x -q`
- `app.*` imports work because `pytest.ini` sets `pythonpath = .`

## Frontend commands (workdir: `frontend/`)
```sh
npm run dev          # dev server (port 5173, proxies /api → localhost:8000)
npm run type-check   # vue-tsc --build (NOT plain tsc)
npm run test:unit    # vitest
npm run test:e2e     # playwright test (needs `npx playwright install` first)
npm run lint         # oxlint then eslint (sequential, not parallel)
npm run build        # type-check + vite build (parallel)
npm run format       # prettier --write --experimental-cli src/
```
- Requires Node `^22.18.0 || >=24.12.0`.
- **Auto-import**: `unplugin-auto-import` injects Vue APIs (`ref`, `computed`, etc.), vue-router, and `ElMessage`/`ElMessageBox`. `unplugin-vue-components` injects Element Plus components. Do NOT manually import these — they are globally available without imports.
- `@/` path alias maps to `src/`.
- **Prettier**: `semi: false`, `singleQuote: true`, `printWidth: 100`.
- **Router guard** (`src/router/index.ts`): `meta.auth` routes redirect to `/login` when no token; `meta.guest` routes redirect to `/novels` when token exists.

## Architecture notes
- **Layer flow**: `api/` (routes) → `services/` (business logic) → `repositories/` (DB queries) → `models/` (SQLAlchemy ORM)
- **API prefix**: all routes mount under `/api/v1` (see `backend/app/main.py`)
- **Route nesting**: `memory`, `writing`, and `ai` routers all nest under `/novels/{novel_id}/` — there are no root-level resource paths
- **Unified response**: all endpoints return `{"code": 0, "message": "ok", "data": ...}` via `ApiResponse.success()` / `ApiResponse.error()`
- **Auth**: bcrypt passwords, HS256 JWT with `user_id` in payload, Bearer token via `get_current_user()` dependency
- **Ownership guards**: `MemoryService.ensure_owned_novel()` and `NovelService.get()` raise `NotFound` for both "not found" and "not owned" (security — avoids leaking novel existence). Mutation methods like `NovelService.update()` raise `Forbidden` separately.
- **Frontend API client**: `src/api/client.ts` — axios instance, request interceptor attaches token from localStorage, response interceptor unwraps `ApiResponse` and redirects to `/login` on 401

## AI module (`backend/app/ai/`)
- LangChain 1.x ReAct agent with `langchain-deepseek` provider
- Agent factory: `create_novel_agent("flash"|"pro")` and `create_novel_deep_agent()` in `agent.py`
- Extraction endpoint: `POST /api/v1/novels/{novel_id}/chapters/{chapter_id}/extract` (body: `{"mode": "standard"|"deep"}`)
- Tools: `get_chapter_context` (reads chapter + memory), `save_character_changes`, `save_plot_facts`, `save_world_settings`, `save_foreshadowing_candidates` (all write to PendingMemory)
- PendingMemory endpoints (all nested under `/api/v1/novels/{novel_id}/`): `GET /pending-memories`, `PUT /pending-memories/{id}/confirm`, `PUT /pending-memories/{id}/reject`, `PUT /pending-memories/batch`
- Requires `DEEPSEEK_API_KEY` in `.env`; models are `deepseek-v4-flash` and `deepseek-v4-pro` (hardcoded in `app/ai/config.py`, NOT `app/core/config.py`)

## Writing module (`backend/app/api/writing.py`, `app/services/writing_service.py`, `app/models/writing.py`)
- Autonomous writing loop (v2): blueprint → chapter plan → chapter brief → context package → writing run → (quality gate) → accept/discard
- All endpoints nested under `/api/v1/novels/{novel_id}/...`: `/blueprints/*`, `/chapter-plans/*`, `/chapter-briefs/*`, `/context-packages/*`, `/writing-runs/*`, `/writing/repairs/*`
- **WritingRun lifecycle**: `POST /writing-runs` runs draft generation + quality gate synchronously. `PUT /writing-runs/{id}/accept` writes draft into a Chapter (new or existing). `PUT /writing-runs/{id}/discard` marks it discarded.
- **Quality gate** (`app/ai/quality_gate.py`): 7 agent types (`task_completion`, `style`, `character`, `continuity`, `world`, `foreshadowing`, `length`). Runs an auto-fix rewrite loop (max 3 iterations) inside `create_writing_run()`. Issues that need author intent become `PendingRepair` rows.
- **PendingRepair status**: `"pending"` → `"applied"` | `"dismissed"` (resolved via `PUT /writing/repairs/{repair_id}/resolve` with `{"action": "apply"|"dismiss"}`).
- **Test injection**: `WritingService(generator=..., gate_agent=...)` accepts fakes (`FakeWritingGenerator`, `FakeQualityGateAgent`) so tests avoid real DeepSeek calls.

## Key data
- **Chapter status**: `"draft"` | `"reviewed"` | `"locked"`
- **WritingRun status**: `"running"` | `"completed"` | `"failed"` | `"accepted"` | `"discarded"`
- **WorldSetting category**: `"geography"` | `"faction"` | `"rule"` | `"history"` | `"culture"` | `"other"`
- **CharacterProfile.behavior_rules**: JSON list of strings
- **Foreshadowing status**: `"planted"` | `"developing"` | `"resolved"`
- **PendingMemory memory_type**: `"character_change"` | `"plot_fact"` | `"world_setting"` | `"foreshadowing"`
- **Error code convention**: HTTP status + 2-digit sequence (e.g. `40400` = first 404 variant); defined in `backend/app/core/exceptions.py`
- **Token expiry**: default 1440 minutes (24h), configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`

## Project docs
- `docs/novel-agent系统需求文档第一版.md` — original v1 requirements (long-term memory focused)
- `docs/novel-agent系统需求文档第二版.md` — v2 requirements (autonomous writing loop: blueprint → plan → brief → write → review → memory)
- `docs/superpowers/specs/` — design specs for each phase
- `docs/superpowers/plans/` — implementation plans for each phase


