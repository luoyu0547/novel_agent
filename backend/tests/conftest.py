import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

TEST_DB_PATH = Path(__file__).resolve().parents[1] / "test_novel_agent.db"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret-key"

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Chapter, CharacterProfile, Novel, User, WorldSetting  # noqa: F401, E402


@pytest.fixture(autouse=True)
async def reset_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
