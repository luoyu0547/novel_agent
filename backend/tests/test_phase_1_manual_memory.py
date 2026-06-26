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
        json={"title": "记忆测试小说", "description": "测试"},
    )
    assert response.status_code == 200
    return response.json()["data"]


async def test_novel_and_chapter_manual_memory_fields(client):
    headers = await register_headers(client, "author_one")

    novel_response = await client.post(
        "/api/v1/novels",
        headers=headers,
        json={
            "title": "长夜纪事",
            "description": "边境与皇室的长篇故事",
            "genre": "古风权谋",
            "style_guide": "第三人称有限视角，克制冷调，少用网络化表达。",
        },
    )
    assert novel_response.status_code == 200
    novel = novel_response.json()["data"]
    assert novel["genre"] == "古风权谋"
    assert novel["style_guide"] == "第三人称有限视角，克制冷调，少用网络化表达。"

    updated_response = await client.put(
        f"/api/v1/novels/{novel['id']}",
        headers=headers,
        json={
            "title": "长夜纪事",
            "genre": "古风悬疑",
            "style_guide": "第三人称有限视角，章节末尾保留悬念。",
        },
    )
    assert updated_response.status_code == 200
    updated = updated_response.json()["data"]
    assert updated["genre"] == "古风悬疑"
    assert updated["style_guide"] == "第三人称有限视角，章节末尾保留悬念。"

    chapter_response = await client.post(
        f"/api/v1/novels/{novel['id']}/chapters",
        headers=headers,
        json={
            "title": "第一章 雪线",
            "content": "雪落在城门前。",
            "summary": "女主抵达边城，第一次看见皇室密令。",
            "status": "reviewed",
        },
    )
    assert chapter_response.status_code == 200
    chapter = chapter_response.json()["data"]
    assert chapter["summary"] == "女主抵达边城，第一次看见皇室密令。"
    assert chapter["status"] == "reviewed"

    chapter_update = await client.put(
        f"/api/v1/novels/{novel['id']}/chapters/{chapter['id']}",
        headers=headers,
        json={"summary": "女主抵达边城，并隐约察觉密令与旧案有关。", "status": "locked"},
    )
    assert chapter_update.status_code == 200
    updated_chapter = chapter_update.json()["data"]
    assert updated_chapter["summary"] == "女主抵达边城，并隐约察觉密令与旧案有关。"
    assert updated_chapter["status"] == "locked"


async def test_character_profile_crud(client):
    headers = await register_headers(client, "character_author")
    novel = await create_novel(client, headers)

    created_response = await client.post(
        f"/api/v1/novels/{novel['id']}/characters",
        headers=headers,
        json={
            "name": "沈照夜",
            "story_role": "男主 / 皇室线关键知情人",
            "identity": "边境军少将军",
            "personality": "克制、谨慎、嘴硬心软",
            "motivation": "查清旧案并保护边境",
            "speech_style": "短句，少解释，紧张时更少称呼。",
            "behavior_rules": ["不会主动背叛朋友", "不会在公开场合示弱"],
            "current_state": "刚与女主建立不稳定同盟",
        },
    )
    assert created_response.status_code == 200
    character = created_response.json()["data"]
    assert character["story_role"] == "男主 / 皇室线关键知情人"
    assert character["identity"] == "边境军少将军"
    assert character["behavior_rules"] == ["不会主动背叛朋友", "不会在公开场合示弱"]

    list_response = await client.get(f"/api/v1/novels/{novel['id']}/characters", headers=headers)
    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()["data"]] == ["沈照夜"]

    update_response = await client.put(
        f"/api/v1/novels/{novel['id']}/characters/{character['id']}",
        headers=headers,
        json={"current_state": "决定暂时相信女主", "behavior_rules": ["不会主动背叛朋友"]},
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["current_state"] == "决定暂时相信女主"
    assert updated["behavior_rules"] == ["不会主动背叛朋友"]

    delete_response = await client.delete(
        f"/api/v1/novels/{novel['id']}/characters/{character['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 200
    empty_response = await client.get(f"/api/v1/novels/{novel['id']}/characters", headers=headers)
    assert empty_response.json()["data"] == []


async def test_world_setting_crud_and_cross_user_protection(client):
    owner_headers = await register_headers(client, "setting_owner")
    other_headers = await register_headers(client, "setting_intruder")
    novel = await create_novel(client, owner_headers)

    created_response = await client.post(
        f"/api/v1/novels/{novel['id']}/settings",
        headers=owner_headers,
        json={"title": "北境军制", "category": "rule", "content": "边境军不受地方节度使调动。"},
    )
    assert created_response.status_code == 200
    setting = created_response.json()["data"]
    assert setting["category"] == "rule"

    blocked_response = await client.get(f"/api/v1/novels/{novel['id']}/settings", headers=other_headers)
    assert blocked_response.status_code == 404

    invalid_response = await client.post(
        f"/api/v1/novels/{novel['id']}/settings",
        headers=owner_headers,
        json={"title": "错误分类", "category": "magic", "content": "无效"},
    )
    assert invalid_response.status_code == 422

    update_response = await client.put(
        f"/api/v1/novels/{novel['id']}/settings/{setting['id']}",
        headers=owner_headers,
        json={"content": "边境军只听虎符和皇令。"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["content"] == "边境军只听虎符和皇令。"

    delete_response = await client.delete(
        f"/api/v1/novels/{novel['id']}/settings/{setting['id']}",
        headers=owner_headers,
    )
    assert delete_response.status_code == 200
