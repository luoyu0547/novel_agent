# Novel Agent Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a FastAPI backend with user auth, novel/chapter management, unified response format, and error handling.

**Architecture:** Layered (api -> service -> repository -> model) with dependency injection via FastAPI's `Depends`. SQLAlchemy 2.0 async for ORM, Alembic for migrations, JWT for auth.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), Alembic, PyJWT, passlib[bcrypt], Pydantic v2, aiosqlite (dev), aiomysql (prod)

## Global Constraints

- All API responses must use unified format: `{"code": int, "message": str, "data": any}`
- Internal error details must NOT leak to frontend (return generic message, log server-side)
- Dev environment uses SQLite, prod uses MySQL
- Startup logs must be concise: env, db type, host:port, route count
- No comments in code unless asked
- Python 3.11+, async throughout

---

### Task 1: Project Scaffolding & Core Modules

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/database.py`

**Interfaces:**
- Consumes: (nothing — first task)
- Produces: `Settings` config class, `get_db()` async session generator, `Base` declarative base, `engine` and `AsyncSession` factory

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy[asyncio]>=2.0.25
aiosqlite>=0.19.0
aiomysql>=0.2.0
pymysql>=1.1.0
alembic>=1.13.0
pyjwt>=2.8.0
passlib[bcrypt]>=1.7.4
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
```

- [ ] **Step 2: Create .env.example**

```env
APP_ENV=dev
DATABASE_URL=sqlite+aiosqlite:///./novel_agent.db
SECRET_KEY=change-this-to-a-random-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

- [ ] **Step 3: Create config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "dev"
    DATABASE_URL: str = "sqlite+aiosqlite:///./novel_agent.db"
    SECRET_KEY: str = "change-this-to-a-random-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @property
    def db_driver(self) -> str:
        return "MySQL" if self.is_prod else "SQLite"

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 4: Create database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
```

### Task 2: Unified Response & Error Handling

**Files:**
- Create: `backend/app/core/response.py`
- Create: `backend/app/core/exceptions.py`

**Interfaces:**
- Consumes: nothing from Task 1
- Produces: `ApiResponse` class, `AppException` class, error codes constants

- [ ] **Step 1: Create exceptions.py**

```python
class AppException(Exception):
    def __init__(self, code: int, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


class NotFound(AppException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(code=40400, message=message, status_code=404)


class Unauthorized(AppException):
    def __init__(self, message: str = "未登录或 token 已过期"):
        super().__init__(code=40100, message=message, status_code=401)


class Forbidden(AppException):
    def __init__(self, message: str = "权限不足"):
        super().__init__(code=40300, message=message, status_code=403)


class BadRequest(AppException):
    def __init__(self, code: int = 40000, message: str = "请求参数错误"):
        super().__init__(code=code, message=message, status_code=400)
```

- [ ] **Step 2: Create response.py**

```python
from typing import Any

from fastapi.responses import JSONResponse

from app.core.exceptions import AppException


class ApiResponse:
    @staticmethod
    def success(data: Any = None, message: str = "ok") -> JSONResponse:
        return JSONResponse(content={"code": 0, "message": message, "data": data})

    @staticmethod
    def error(code: int, message: str, status_code: int = 400) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"code": code, "message": message, "data": None},
        )
```

### Task 3: Global Exception Handlers

**Files:**
- Create: `backend/app/core/handlers.py`

**Interfaces:**
- Consumes: `AppException` from Task 2, `ApiResponse` from Task 2
- Produces: `register_exception_handlers(app)` function — attaches handlers to the FastAPI app

- [ ] **Step 1: Create handlers.py**

```python
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException

logger = logging.getLogger("novel_agent")


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "data": None},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"code": 50000, "message": "服务器内部错误", "data": None},
        )
```

### Task 4: User Model & Repository

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/repositories/__init__.py`
- Create: `backend/app/repositories/user_repo.py`

**Interfaces:**
- Consumes: `Base`, `get_db` from Task 1
- Produces: `User` model with `id`, `username`, `hashed_password`, `created_at`, `updated_at`

- [ ] **Step 1: Create models/__init__.py**

```python
from app.models.user import User
from app.models.novel import Novel, Chapter

__all__ = ["User", "Novel", "Chapter"]
```

- [ ] **Step 2: Create models/user.py**

```python
import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    novels = relationship("Novel", back_populates="user")
```

- [ ] **Step 3: Create repositories/__init__.py** (empty)

- [ ] **Step 4: Create repositories/user_repo.py**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, username: str, hashed_password: str) -> User:
        user = User(username=username, hashed_password=hashed_password)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)
```

### Task 5: Security (JWT & Password Hashing)

**Files:**
- Create: `backend/app/core/security.py`

**Interfaces:**
- Consumes: `settings` from Task 1
- Produces: `hash_password(plain)`, `verify_password(plain, hashed)`, `create_token(data)`, `decode_token(token)`, `get_current_user(token, db)` dependency

- [ ] **Step 1: Create security.py**

```python
import datetime
import logging

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import Unauthorized
from app.models.user import User
from app.repositories.user_repo import UserRepo

logger = logging.getLogger("novel_agent")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise Unauthorized("token 已过期")
    except jwt.InvalidTokenError:
        raise Unauthorized("无效的 token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    user_id = payload.get("user_id")
    if not user_id:
        raise Unauthorized("无效的 token")
    user = await UserRepo(db).get_by_id(user_id)
    if not user:
        raise Unauthorized("用户不存在")
    return user
```

### Task 6: Auth Schemas & Service

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/auth_service.py`

**Interfaces:**
- Consumes: `UserRepo` from Task 4, `hash_password`, `verify_password`, `create_token` from Task 5
- Produces: `AuthService.register(username, password)`, `AuthService.login(username, password)`

- [ ] **Step 1: Create schemas/__init__.py** (empty)

- [ ] **Step 2: Create schemas/auth.py**

```python
from pydantic import BaseModel, field_validator


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 2 or len(v) > 50:
            raise ValueError("用户名长度应在 2-50 个字符之间")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码长度不能少于 6 个字符")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: int
    username: str
```

- [ ] **Step 3: Create services/__init__.py** (empty)

- [ ] **Step 4: Create services/auth_service.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, Unauthorized
from app.core.security import create_token, hash_password, verify_password
from app.repositories.user_repo import UserRepo


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepo(db)

    async def register(self, username: str, password: str) -> dict:
        existing = await self.repo.get_by_username(username)
        if existing:
            raise BadRequest(code=40001, message="用户名已存在")
        hashed = hash_password(password)
        user = await self.repo.create(username, hashed)
        token = create_token({"user_id": user.id})
        return {"token": token, "user_id": user.id, "username": user.username}

    async def login(self, username: str, password: str) -> dict:
        user = await self.repo.get_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            raise Unauthorized("用户名或密码错误")
        token = create_token({"user_id": user.id})
        return {"token": token, "user_id": user.id, "username": user.username}
```

### Task 7: Auth API Routes

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/auth.py`

**Interfaces:**
- Consumes: `AuthService` from Task 6, `ApiResponse` from Task 2, `RegisterRequest`/`LoginRequest` from Task 6
- Produces: `register` and `login` endpoint functions

- [ ] **Step 1: Create api/__init__.py** (empty)

- [ ] **Step 2: Create api/auth.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await AuthService(db).register(body.username, body.password)
    return ApiResponse.success(data=result, message="注册成功")


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await AuthService(db).login(body.username, body.password)
    return ApiResponse.success(data=result, message="登录成功")
```

### Task 8: Novel & Chapter Models

**Files:**
- Create: `backend/app/models/novel.py`

**Interfaces:**
- Consumes: `Base`, `User` model from Task 4
- Produces: `Novel` model, `Chapter` model

- [ ] **Step 1: Create models/novel.py**

```python
import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    user = relationship("User", back_populates="novels")
    chapters = relationship("Chapter", back_populates="novel", order_by="Chapter.created_at")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)

    novel = relationship("Novel", back_populates="chapters")
```

### Task 9: Novel Repository

**Files:**
- Create: `backend/app/repositories/novel_repo.py`
- Modify: `backend/app/models/user.py` (add novels relationship if not already there)

**Interfaces:**
- Consumes: `Novel`, `Chapter` models from Task 8
- Produces: `NovelRepo` and `ChapterRepo` with CRUD methods

- [ ] **Step 1: Create repositories/novel_repo.py**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.novel import Chapter, Novel


class NovelRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, title: str, description: str | None = None) -> Novel:
        novel = Novel(user_id=user_id, title=title, description=description)
        self.db.add(novel)
        await self.db.commit()
        await self.db.refresh(novel)
        return novel

    async def list_by_user(self, user_id: int) -> list[Novel]:
        result = await self.db.execute(
            select(Novel).where(Novel.user_id == user_id).order_by(Novel.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, novel_id: int) -> Novel | None:
        result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id).options(selectinload(Novel.chapters))
        )
        return result.scalar_one_or_none()

    async def update(self, novel: Novel, title: str | None, description: str | None) -> Novel:
        if title is not None:
            novel.title = title
        if description is not None:
            novel.description = description
        await self.db.commit()
        await self.db.refresh(novel)
        return novel

    async def delete(self, novel: Novel) -> None:
        await self.db.delete(novel)
        await self.db.commit()


class ChapterRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, novel_id: int, title: str, content: str = "") -> Chapter:
        chapter = Chapter(novel_id=novel_id, title=title, content=content)
        self.db.add(chapter)
        await self.db.commit()
        await self.db.refresh(chapter)
        return chapter

    async def get_by_id(self, chapter_id: int) -> Chapter | None:
        return await self.db.get(Chapter, chapter_id)

    async def update(self, chapter: Chapter, title: str | None, content: str | None) -> Chapter:
        if title is not None:
            chapter.title = title
        if content is not None:
            chapter.content = content
        await self.db.commit()
        await self.db.refresh(chapter)
        return chapter

    async def delete(self, chapter: Chapter) -> None:
        await self.db.delete(chapter)
        await self.db.commit()
```

### Task 10: Novel Schemas & Service

**Files:**
- Create: `backend/app/schemas/novel.py`
- Create: `backend/app/services/novel_service.py`

**Interfaces:**
- Consumes: `NovelRepo`, `ChapterRepo` from Task 9, `NotFound` from Task 2
- Produces: `NovelService` with full CRUD, Pydantic schemas for novel/chapter

- [ ] **Step 1: Create schemas/novel.py**

```python
import datetime

from pydantic import BaseModel


class NovelCreate(BaseModel):
    title: str
    description: str | None = None


class NovelUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class ChapterCreate(BaseModel):
    title: str
    content: str = ""


class ChapterUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class ChapterOut(BaseModel):
    id: int
    novel_id: int
    title: str
    content: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class NovelOut(BaseModel):
    id: int
    title: str
    description: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    chapters: list[ChapterOut] | None = None

    model_config = {"from_attributes": True}


class NovelListItem(BaseModel):
    id: int
    title: str
    description: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Create services/novel_service.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Forbidden, NotFound
from app.repositories.novel_repo import ChapterRepo, NovelRepo


class NovelService:
    def __init__(self, db: AsyncSession):
        self.repo = NovelRepo(db)
        self.chapter_repo = ChapterRepo(db)

    async def create(self, user_id: int, title: str, description: str | None = None):
        return await self.repo.create(user_id, title, description)

    async def list(self, user_id: int):
        return await self.repo.list_by_user(user_id)

    async def get(self, novel_id: int):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        return novel

    async def update(self, user_id: int, novel_id: int, title: str | None, description: str | None):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise Forbidden("无权修改该小说")
        return await self.repo.update(novel, title, description)

    async def delete(self, user_id: int, novel_id: int):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise Forbidden("无权删除该小说")
        await self.repo.delete(novel)

    async def create_chapter(self, user_id: int, novel_id: int, title: str, content: str = ""):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise Forbidden("无权在该小说下创建章节")
        return await self.chapter_repo.create(novel_id, title, content)

    async def get_chapter(self, novel_id: int, chapter_id: int):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter or chapter.novel_id != novel_id:
            raise NotFound("章节不存在")
        return chapter

    async def update_chapter(self, user_id: int, novel_id: int, chapter_id: int, title: str | None, content: str | None):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise Forbidden("无权修改该章节")
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter or chapter.novel_id != novel_id:
            raise NotFound("章节不存在")
        return await self.chapter_repo.update(chapter, title, content)

    async def delete_chapter(self, user_id: int, novel_id: int, chapter_id: int):
        novel = await self.repo.get_by_id(novel_id)
        if not novel:
            raise NotFound("小说不存在")
        if novel.user_id != user_id:
            raise Forbidden("无权删除该章节")
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter or chapter.novel_id != novel_id:
            raise NotFound("章节不存在")
        await self.chapter_repo.delete(chapter)
```

### Task 11: Novel API Routes

**Files:**
- Create: `backend/app/api/novels.py`

**Interfaces:**
- Consumes: `NovelService` from Task 10, `ApiResponse` from Task 2, `get_current_user` from Task 5
- Produces: All novel/chapter endpoint functions

- [ ] **Step 1: Create api/novels.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ApiResponse
from app.models.user import User
from app.core.security import get_current_user
from app.schemas.novel import ChapterCreate, ChapterUpdate, NovelCreate, NovelUpdate
from app.services.novel_service import NovelService

router = APIRouter(prefix="/novels", tags=["小说"])


@router.get("")
async def list_novels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    novels = await NovelService(db).list(current_user.id)
    return ApiResponse.success(data=novels)


@router.post("")
async def create_novel(
    body: NovelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    novel = await NovelService(db).create(current_user.id, body.title, body.description)
    return ApiResponse.success(data=novel, message="小说创建成功")


@router.get("/{novel_id}")
async def get_novel(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    novel = await NovelService(db).get(novel_id)
    return ApiResponse.success(data=novel)


@router.put("/{novel_id}")
async def update_novel(
    novel_id: int,
    body: NovelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    novel = await NovelService(db).update(current_user.id, novel_id, body.title, body.description)
    return ApiResponse.success(data=novel, message="小说更新成功")


@router.delete("/{novel_id}")
async def delete_novel(
    novel_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).delete(current_user.id, novel_id)
    return ApiResponse.success(message="小说删除成功")


@router.post("/{novel_id}/chapters")
async def create_chapter(
    novel_id: int,
    body: ChapterCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chapter = await NovelService(db).create_chapter(current_user.id, novel_id, body.title, body.content)
    return ApiResponse.success(data=chapter, message="章节创建成功")


@router.get("/{novel_id}/chapters/{chapter_id}")
async def get_chapter(
    novel_id: int,
    chapter_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chapter = await NovelService(db).get_chapter(novel_id, chapter_id)
    return ApiResponse.success(data=chapter)


@router.put("/{novel_id}/chapters/{chapter_id}")
async def update_chapter(
    novel_id: int,
    chapter_id: int,
    body: ChapterUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chapter = await NovelService(db).update_chapter(current_user.id, novel_id, chapter_id, body.title, body.content)
    return ApiResponse.success(data=chapter, message="章节保存成功")


@router.delete("/{novel_id}/chapters/{chapter_id}")
async def delete_chapter(
    novel_id: int,
    chapter_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NovelService(db).delete_chapter(current_user.id, novel_id, chapter_id)
    return ApiResponse.success(message="章节删除成功")
```

### Task 12: Main App Entry & Alembic Setup

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/.gitkeep`

**Interfaces:**
- Consumes: all routes, error handlers, database engine
- Produces: runnable FastAPI application

- [ ] **Step 1: Create main.py**

```python
import logging

import uvicorn
from fastapi import FastAPI

from app.api import auth, novels
from app.core.config import settings
from app.core.database import engine, Base
from app.core.handlers import register_exception_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("novel_agent")


def create_app() -> FastAPI:
    app = FastAPI(title="Novel Agent", version="0.1.0")

    register_exception_handlers(app)

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(novels.router, prefix="/api/v1")

    @app.on_event("startup")
    async def startup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Environment: %s", settings.APP_ENV)
        logger.info("Database: %s", settings.db_driver)
        routes_count = len([r for r in app.routes if hasattr(r, "methods")])
        logger.info("Routes registered: %d", routes_count)

    @app.on_event("shutdown")
    async def shutdown():
        await engine.dispose()

    return app


app = create_app()

if __name__ == "__main__":
    logger.info("Starting server at http://0.0.0.0:8000")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 2: Verify app starts successfully**

```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
python -m app.main
```

Expected: Server starts at http://0.0.0.0:8000 with logs showing env, db type, and route count.

- [ ] **Step 3: Test the API with curl**

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "123456"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "123456"}'

# Create novel (use token from login)
curl -X POST http://localhost:8000/api/v1/novels \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"title": "我的第一部小说", "description": "这是一部伟大的作品"}'

# Create chapter
curl -X POST http://localhost:8000/api/v1/novels/1/chapters \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"title": "第一章", "content": "很久很久以前..."}'
```

- [ ] **Step 4: Initialize git and commit**

```bash
cd /Users/luoyu/code/novel-agent
git add backend/ docs/
git commit -m "feat: initialize backend with FastAPI scaffolding

- Layered architecture (api/service/repository/model)
- User auth with JWT
- Novel & Chapter CRUD
- Unified response format & error handling
- SQLite for dev, MySQL-ready config
- Alembic migration setup"
```
