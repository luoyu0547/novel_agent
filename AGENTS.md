# Novel Agent

## Project structure
- `backend/` — FastAPI (Python 3.12, async SQLAlchemy, SQLite dev / MySQL prod)
- `frontend/` — Vue 3 + TypeScript + Pinia + Vite

## Backend commands
```sh
.venv/bin/python -m uvicorn app.main:app --reload   # dev server (port 8000)
.venv/bin/python -m pytest tests/ -x -q              # run all tests
.venv/bin/python -m alembic upgrade head             # run migrations
```
- Tests use `conftest.py` which sets `APP_ENV=test`, overrides `DATABASE_URL` to `test_novel_agent.db`, and resets DB per test via autouse fixture.
- Run a single test: `.venv/bin/python -m pytest tests/test_phase_1_manual_memory.py::test_character_profile_crud -x -q`
- All `app.*` imports work because `pytest.ini` sets `pythonpath = .`
- First-time setup: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cp .env.example .env`

## Frontend commands
```sh
npm run dev          # dev server (port 5173, proxies /api → localhost:8000)
npm run type-check   # vue-tsc --build (NOT plain tsc)
npm run test:unit    # vitest
npm run test:e2e     # playwright test
npm run lint         # oxlint then eslint (sequential, not parallel)
npm run build        # type-check + vite build
npm run format       # prettier --write src/
```

## Architecture notes
- **Layer flow**: `api/` (routes) → `services/` (business logic) → `repositories/` (DB queries) → `models/` (SQLAlchemy ORM)
- **Unified response**: all endpoints return `{"code": 0, "message": "ok", "data": ...}` via `ApiResponse.success()` / `ApiResponse.error()`
- **Ownership guards**: `MemoryService.ensure_owned_novel()` and `NovelService.get()` raise `NotFound` for both "not found" and "not owned" (security — avoids leaking novel existence). `NovelService` mutation methods raise `Forbidden` when ownership check fails separately.
- **Auth**: bcrypt passwords, HS256 JWT with `user_id` in payload, Bearer token via `get_current_user()` dependency
- **Frontend API client**: axios instance in `src/api/client.ts` — request interceptor attaches token from localStorage, response interceptor unwraps `ApiResponse` and redirects to `/login` on 401

## Key data
- **Chapter status**: `"draft"` | `"reviewed"` | `"locked"` (enforced by `ChapterStatus` literal)
- **WorldSetting category**: `"geography"` | `"faction"` | `"rule"` | `"history"` | `"culture"` | `"other"`
- **CharacterProfile.behavior_rules**: stored as JSON list of strings
- **Error code convention**: HTTP status + 2-digit sequence (e.g. `40400` = first 404 variant)
- **Token expiry**: default 1440 minutes (24h), configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`
