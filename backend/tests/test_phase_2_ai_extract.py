"""Phase 2 AI 提取集成测试——调用真实 DeepSeek API。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not settings.DEEPSEEK_API_KEY,
        reason="DEEPSEEK_API_KEY not set — set in .env to run AI tests",
    ),
]


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """注册并登录，返回 Authorization header。"""
    await client.post("/api/v1/auth/register", json={"username": "test_ai", "password": "pass123"})
    resp = await client.post("/api/v1/auth/login", json={"username": "test_ai", "password": "pass123"})
    token = resp.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def novel_chapter(client: AsyncClient, auth_headers: dict) -> tuple[int, int]:
    """创建测试小说和章节，返回 (novel_id, chapter_id)。"""
    resp = await client.post("/api/v1/novels", json={"title": "AI测试小说"}, headers=auth_headers)
    novel_id = resp.json()["data"]["id"]

    # 创建角色
    await client.post(f"/api/v1/novels/{novel_id}/characters", json={
        "name": "主角",
        "story_role": "protagonist",
        "personality": "冷静谨慎，重情义",
        "current_state": "离家出走中",
    }, headers=auth_headers)

    # 创建设定
    await client.post(f"/api/v1/novels/{novel_id}/settings", json={
        "title": "青云城",
        "category": "geography",
        "content": "边境要塞城市，常年风雪",
    }, headers=auth_headers)

    # 创建章节
    resp = await client.post(f"/api/v1/novels/{novel_id}/chapters", json={
        "title": "第一章 风雪夜归人",
        "content": (
            "青云城的冬天格外漫长。主角裹紧了大氅，在城门口遇到了一个受伤的陌生人。"
            "那人脸色苍白，胸前一道深可见骨的伤口还在渗血。"
            "主角犹豫了片刻，还是把他扶进了城中唯一的客栈。"
            "客栈老板娘认得主角，惊讶地问：'你怎么回来了？'"
            "主角没有回答。他盯着陌生人腰间那枚玉佩，瞳孔微缩——"
            "那是他十年前送给妹妹的信物。"
        ),
    }, headers=auth_headers)
    chapter_id = resp.json()["data"]["id"]
    return novel_id, chapter_id


@pytest.mark.asyncio
async def test_extract_chapter_basic(client: AsyncClient, auth_headers: dict, novel_chapter: tuple[int, int]):
    """测试标准模式提取——验证返回结构正确。"""
    novel_id, chapter_id = novel_chapter
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/extract",
        json={"mode": "standard"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    extract = data["data"]
    assert "pending_ids" in extract
    assert "pending_count" in extract
    assert extract["pending_count"] == len(extract["pending_ids"])


@pytest.mark.asyncio
async def test_extract_chapter_deep(client: AsyncClient, auth_headers: dict, novel_chapter: tuple[int, int]):
    """测试深度模式提取。"""
    novel_id, chapter_id = novel_chapter
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/extract",
        json={"mode": "deep"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    extract = data["data"]
    assert "pending_ids" in extract
    assert "pending_count" in extract
    assert extract["pending_count"] == len(extract["pending_ids"])


@pytest.mark.asyncio
async def test_pending_memory_confirm_flow(client: AsyncClient, auth_headers: dict, novel_chapter: tuple[int, int]):
    """测试完整流程：提取 → 查看待确认 → 确认 → 拒绝。"""
    novel_id, chapter_id = novel_chapter

    # 提取
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/extract",
        json={"mode": "standard"},
        headers=auth_headers,
    )
    pending_ids = resp.json()["data"]["pending_ids"]
    assert len(pending_ids) > 0

    # 查看待确认列表
    resp = await client.get(f"/api/v1/novels/{novel_id}/pending-memories", headers=auth_headers)
    assert resp.status_code == 200
    memories = resp.json()["data"]
    assert len(memories) >= len(pending_ids)

    # 确认第一条
    first_id = pending_ids[0]
    resp = await client.put(
        f"/api/v1/novels/{novel_id}/pending-memories/{first_id}/confirm",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # 拒绝第二条
    if len(pending_ids) > 1:
        second_id = pending_ids[1]
        resp = await client.put(
            f"/api/v1/novels/{novel_id}/pending-memories/{second_id}/reject",
            headers=auth_headers,
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pending_memory_batch(client: AsyncClient, auth_headers: dict, novel_chapter: tuple[int, int]):
    """测试批量操作。"""
    novel_id, chapter_id = novel_chapter

    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/extract",
        json={"mode": "standard"},
        headers=auth_headers,
    )
    pending_ids = resp.json()["data"]["pending_ids"]
    if not pending_ids:
        pytest.skip("No pending memories created")

    resp = await client.put(
        f"/api/v1/novels/{novel_id}/pending-memories/batch",
        json={"ids": pending_ids, "action": "confirm"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_extract_unauthorized(client: AsyncClient, novel_chapter: tuple[int, int]):
    """未认证用户不能调用提取。"""
    novel_id, chapter_id = novel_chapter
    resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/extract",
        json={"mode": "standard"},
    )
    assert resp.status_code == 401
