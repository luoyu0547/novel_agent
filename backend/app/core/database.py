"""异步 SQLAlchemy 引擎、会话工厂和 Base 基类。

``expire_on_commit=False`` 避免异步模式下提交后的懒加载问题。
``get_db`` 是一个 FastAPI 依赖，提供会话并在请求结束时自动关闭。
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 SQLAlchemy ORM 模型的基类。"""


async def get_db():
    """FastAPI 依赖：提供异步数据库会话，请求结束后自动关闭。"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
