# Novel Agent Backend Design

## Overview

Novel Agent is a writing tool backend that provides novel/chapter management with user authentication, built with Python FastAPI.

## Tech Stack

| Component | Choice |
|-----------|--------|
| Web Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) |
| Database Migration | Alembic |
| Auth | JWT (PyJWT + passlib/bcrypt) |
| Validation | Pydantic v2 |
| Dev Database | SQLite (aiosqlite) |
| Prod Database | MySQL (aiomysql) |

## Project Structure (Layered Architecture)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py                # register/login routes
│   │   └── novels.py              # novel/chapter CRUD routes
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # env-based config (SQLite/MySQL switch)
│   │   ├── security.py            # JWT generation & verification
│   │   ├── database.py            # engine & session management
│   │   ├── response.py            # unified response wrapper
│   │   └── exceptions.py          # global error handling
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                # User model
│   │   └── novel.py               # Novel + Chapter models
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                # login/register request/response
│   │   └── novel.py               # novel/chapter request/response
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py        # auth business logic
│   │   └── novel_service.py       # novel business logic
│   └── repositories/
│       ├── __init__.py
│       ├── user_repo.py           # user data access
│       └── novel_repo.py          # novel data access
├── alembic/                       # migrations
├── requirements.txt
├── .env.example
└── README.md
```

## Data Models

### User
- `id`: int (PK, auto-increment)
- `username`: str(50), unique, not null
- `hashed_password`: str, not null
- `created_at`: datetime, not null
- `updated_at`: datetime, not null

### Novel
- `id`: int (PK, auto-increment)
- `user_id`: int (FK -> User), not null
- `title`: str(200), not null
- `description`: text, nullable
- `created_at`: datetime, not null
- `updated_at`: datetime, not null

### Chapter
- `id`: int (PK, auto-increment)
- `novel_id`: int (FK -> Novel), not null
- `title`: str(200), not null
- `content`: text, not null (chapter body text)
- `created_at`: datetime, not null
- `updated_at`: datetime, not null

Relations: User 1:N Novel 1:N Chapter

## API Endpoints

```
POST   /api/v1/auth/register                    # Register
POST   /api/v1/auth/login                       # Login, returns JWT

GET    /api/v1/novels                           # List user's novels
POST   /api/v1/novels                           # Create novel
GET    /api/v1/novels/{id}                      # Get novel detail (with chapters)
PUT    /api/v1/novels/{id}                      # Update novel
DELETE /api/v1/novels/{id}                      # Delete novel

POST   /api/v1/novels/{novel_id}/chapters       # Create chapter
GET    /api/v1/novels/{novel_id}/chapters/{id}  # Get chapter content
PUT    /api/v1/novels/{novel_id}/chapters/{id}  # Save/update chapter content
DELETE /api/v1/novels/{novel_id}/chapters/{id}  # Delete chapter
```

- API version prefix: `/api/v1/`
- Auth via `Authorization: Bearer <token>`

## Unified Response Format

```json
// Success
{ "code": 0, "message": "ok", "data": { ... } }

// Error
{ "code": 40001, "message": "具体错误信息", "data": null }
```

### Error Codes

| Range | Meaning |
|-------|---------|
| 0 | Success |
| 400xx | Bad request / validation error |
| 401xx | Authentication (unauthorized, token expired) |
| 403xx | Permission denied |
| 404xx | Resource not found |
| 500xx | Server internal error |

## Error Handling

- Custom `AppException(Exception)` with `code` + `message` + `status_code`
- Global `@app.exception_handler(AppException)` catches all business errors
- Global `@app.exception_handler(Exception)` catches unexpected errors — returns generic "服务器内部错误" without exposing internal details
- All internal errors and stack traces are logged server-side only

## Configuration

```env
APP_ENV=dev                    # dev | prod
DATABASE_URL=sqlite+aiosqlite:///./novel_agent.db
# DATABASE_URL=mysql+aiomysql://user:pass@host/novel_agent?charset=utf8mb4
SECRET_KEY=<random-secret>
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

- SQLite for development/testing, MySQL for production
- Controlled via `APP_ENV` or direct `DATABASE_URL` override

## Key Startup Logs

On boot, the app logs (not excessively):
- App environment (dev/prod)
- Database type (SQLite/MySQL)
- Listening host and port
- Number of registered routes

## OSS Migration Path

Chapter content is stored in `Chapter.content` as text. When OSS is needed:
1. Add OSS config to `core/config.py`
2. Upload content to OSS on save, store the object key instead of content text
3. Service layer abstracts this — API consumers won't notice the change
