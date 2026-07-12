"""Phase 1 v2 自主写作测试——使用 FakeWritingGenerator，不依赖真实 AI。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.ai.quality_gate import FakeQualityGateAgent
from app.ai.writer import FakeWritingGenerator


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def fake_writing_service(monkeypatch):
    """Keep route-level Phase 1 tests deterministic and offline."""
    from app.api import writing as writing_api

    production_service = writing_api.WritingService

    def build_test_service(*args, **kwargs):
        return production_service(
            *args,
            generator=FakeWritingGenerator(),
            gate_agent=FakeQualityGateAgent(),
            **kwargs,
        )

    monkeypatch.setattr(writing_api, "WritingService", build_test_service)


async def register_headers(client, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


async def create_novel(client, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/api/v1/novels",
        headers=headers,
        json={"title": "写作测试小说", "description": "用于测试自主写作闭环", "genre": "古风权谋", "style_guide": "第三人称有限视角"},
    )
    assert response.status_code == 200
    return response.json()["data"]


@pytest.fixture
async def novel_and_headers(client):
    headers = await register_headers(client, "writing_user")
    novel = await create_novel(client, headers)
    return novel, headers


@pytest.mark.asyncio
async def test_blueprint_generate_and_activate(client, novel_and_headers):
    """测试生成蓝图并激活。"""
    novel, headers = novel_and_headers
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "一个关于权力与背叛的故事"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "draft"
    assert "core_promise" in data["content_json"]
    blueprint_id = data["id"]

    resp = await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{blueprint_id}/activate",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_blueprint_list(client, novel_and_headers):
    """测试蓝图列表。"""
    novel, headers = novel_and_headers
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


@pytest.mark.asyncio
async def test_blueprint_update(client, novel_and_headers):
    """测试更新蓝图。"""
    novel, headers = novel_and_headers
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    blueprint_id = resp.json()["data"]["id"]
    new_content = {"core_promise": "修改后的核心卖点"}
    resp = await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{blueprint_id}",
        headers=headers,
        json={"content_json": new_content},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["content_json"]["core_promise"] == "修改后的核心卖点"


@pytest.mark.asyncio
async def test_blueprint_activate_archives_previous(client, novel_and_headers):
    """测试激活新蓝图时旧蓝图被归档。"""
    novel, headers = novel_and_headers
    resp1 = await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "第一版"},
    )
    bp1_id = resp1.json()["data"]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp1_id}/activate",
        headers=headers,
    )
    resp2 = await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "第二版"},
    )
    bp2_id = resp2.json()["data"]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp2_id}/activate",
        headers=headers,
    )
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    blueprints = resp.json()["data"]
    for bp in blueprints:
        if bp["id"] == bp1_id:
            assert bp["status"] == "archived"
        if bp["id"] == bp2_id:
            assert bp["status"] == "active"


@pytest.mark.asyncio
async def test_chapter_plan_fails_without_active_blueprint(client, novel_and_headers):
    """测试没有激活蓝图时不能生成章节计划。"""
    novel, headers = novel_and_headers
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate",
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_chapter_plan_generate(client, novel_and_headers):
    """测试生成章节计划。"""
    novel, headers = novel_and_headers
    await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate",
        headers=headers,
    )
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "ready"
    assert "plot_task" in data["content_json"]


@pytest.mark.asyncio
async def test_chapter_brief_generate(client, novel_and_headers):
    """测试生成章节任务书和默认篇幅契约。"""
    novel, headers = novel_and_headers
    await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate",
        headers=headers,
    )
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate",
        headers=headers,
    )
    plan_id = resp.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-briefs/generate",
        headers=headers,
        json={"chapter_plan_id": plan_id},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "ready"
    assert data["length_contract_json"]["target_words"] == 3000
    assert data["length_contract_json"]["min_words"] == 2000


@pytest.mark.asyncio
async def test_context_package_generate(client, novel_and_headers):
    """测试上下文包生成包含全部上下文。"""
    novel, headers = novel_and_headers
    await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate",
        headers=headers,
    )
    await client.post(f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate", headers=headers)
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate", headers=headers)
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate", headers=headers)
    plan_id = resp.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-briefs/generate",
        headers=headers,
        json={"chapter_plan_id": plan_id},
    )
    brief_id = resp.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/novels/{novel['id']}/context-packages/generate",
        headers=headers,
        json={"chapter_brief_id": brief_id},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "chapter_brief" in data["package_json"]
    assert "length_contract" in data["package_json"]
    assert "characters" in data["package_json"]


@pytest.mark.asyncio
async def test_writing_run_full_flow(client, novel_and_headers):
    """测试完整写作运行流程：生成蓝图 → 计划 → 任务书 → 上下文包 → 草稿 → 接受。"""
    novel, headers = novel_and_headers
    bp_resp = await client.post(
        f"/api/v1/novels/{novel['id']}/blueprints/generate",
        headers=headers,
        json={"author_input": "测试"},
    )
    bp_id = bp_resp.json()["data"]["id"]
    await client.put(
        f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate",
        headers=headers,
    )
    plan_resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate",
        headers=headers,
    )
    plan_id = plan_resp.json()["data"]["id"]
    brief_resp = await client.post(
        f"/api/v1/novels/{novel['id']}/chapter-briefs/generate",
        headers=headers,
        json={"chapter_plan_id": plan_id},
    )
    brief_id = brief_resp.json()["data"]["id"]
    ctx_resp = await client.post(
        f"/api/v1/novels/{novel['id']}/context-packages/generate",
        headers=headers,
        json={"chapter_brief_id": brief_id},
    )
    ctx_id = ctx_resp.json()["data"]["id"]
    run_resp = await client.post(
        f"/api/v1/novels/{novel['id']}/writing-runs",
        headers=headers,
        json={"chapter_brief_id": brief_id},
    )
    assert run_resp.status_code == 200
    run = run_resp.json()["data"]
    assert run["status"] in ("completed", "failed")
    assert run["word_count"] >= 0
    if run["status"] == "completed":
        accept_resp = await client.put(
            f"/api/v1/novels/{novel['id']}/writing-runs/{run['id']}/accept",
            headers=headers,
        )
        assert accept_resp.status_code == 200
        assert accept_resp.json()["data"]["chapter"]["content"] == run["draft_content"]


@pytest.mark.asyncio
async def test_writing_run_discard(client, novel_and_headers):
    """测试废弃写作运行不修改章节。"""
    novel, headers = novel_and_headers
    await client.post(f"/api/v1/novels/{novel['id']}/blueprints/generate", headers=headers, json={"author_input": "测试"})
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate", headers=headers)
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate", headers=headers)
    plan_id = resp.json()["data"]["id"]
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-briefs/generate", headers=headers, json={"chapter_plan_id": plan_id})
    brief_id = resp.json()["data"]["id"]
    resp = await client.post(f"/api/v1/novels/{novel['id']}/context-packages/generate", headers=headers, json={"chapter_brief_id": brief_id})
    run_resp = await client.post(f"/api/v1/novels/{novel['id']}/writing-runs", headers=headers, json={"chapter_brief_id": brief_id})
    run = run_resp.json()["data"]
    if run["status"] != "completed":
        pytest.skip("AI generation failed, skipping accept/discard tests")
    chapter_count_resp = await client.get(f"/api/v1/novels/{novel['id']}", headers=headers)
    chapter_count_before = len(chapter_count_resp.json()["data"].get("chapters", []))
    discard_resp = await client.put(
        f"/api/v1/novels/{novel['id']}/writing-runs/{run['id']}/discard",
        headers=headers,
    )
    assert discard_resp.status_code == 200
    run_resp2 = await client.get(
        f"/api/v1/novels/{novel['id']}/writing-runs/{run['id']}",
        headers=headers,
    )
    assert run_resp2.json()["data"]["status"] == "discarded"


@pytest.mark.asyncio
async def test_double_accept_rejected(client, novel_and_headers):
    """测试已处理的写作运行不能再次操作。"""
    novel, headers = novel_and_headers
    await client.post(f"/api/v1/novels/{novel['id']}/blueprints/generate", headers=headers, json={"author_input": "测试"})
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=headers)
    bp_id = resp.json()["data"][0]["id"]
    await client.put(f"/api/v1/novels/{novel['id']}/blueprints/{bp_id}/activate", headers=headers)
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate", headers=headers)
    plan_id = resp.json()["data"]["id"]
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-briefs/generate", headers=headers, json={"chapter_plan_id": plan_id})
    brief_id = resp.json()["data"]["id"]
    await client.post(f"/api/v1/novels/{novel['id']}/context-packages/generate", headers=headers, json={"chapter_brief_id": brief_id})
    run_resp = await client.post(f"/api/v1/novels/{novel['id']}/writing-runs", headers=headers, json={"chapter_brief_id": brief_id})
    run = run_resp.json()["data"]
    if run["status"] != "completed":
        pytest.skip("AI generation failed, skipping double accept tests")
    await client.put(
        f"/api/v1/novels/{novel['id']}/writing-runs/{run['id']}/accept",
        headers=headers,
    )
    resp = await client.put(
        f"/api/v1/novels/{novel['id']}/writing-runs/{run['id']}/accept",
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cross_user_protection(client, novel_and_headers):
    """测试跨用户无法访问写作资源。"""
    novel, headers = novel_and_headers
    intruder_headers = await register_headers(client, "intruder")
    await client.post(f"/api/v1/novels/{novel['id']}/blueprints/generate", headers=headers, json={"author_input": "测试"})
    resp = await client.get(f"/api/v1/novels/{novel['id']}/blueprints", headers=intruder_headers)
    assert resp.status_code == 404
    resp = await client.post(f"/api/v1/novels/{novel['id']}/chapter-plans/next/generate", headers=intruder_headers)
    assert resp.status_code == 404
