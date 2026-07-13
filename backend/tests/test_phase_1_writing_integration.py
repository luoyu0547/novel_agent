"""Phase 1 v2 自主写作集成测试——调用真实 DeepSeek API。"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not settings.DEEPSEEK_API_KEY,
        reason="DEEPSEEK_API_KEY not set — set in .env to run AI integration tests",
    ),
]


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_headers(client) -> dict:
    await client.post("/api/v1/auth/register", json={"username": "writing_ai", "password": "pass123"})
    resp = await client.post("/api/v1/auth/login", json={"username": "writing_ai", "password": "pass123"})
    token = resp.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_blueprint_generate_real_ai(client, auth_headers):
    """验证真实 AI 能生成包含必需字段的蓝图。"""
    resp = await client.post("/api/v1/novels", json={"title": "蓝图测试", "genre": "都市悬疑"}, headers=auth_headers)
    novel_id = resp.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/blueprints/generate",
        json={"author_input": "一个都市悬疑故事，主角是退役刑警"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "core_promise" in data["content_json"]
    assert "main_conflict" in data["content_json"]
    assert data["status"] == "draft"
