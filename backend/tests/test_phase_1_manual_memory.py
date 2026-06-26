async def register_headers(client, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


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
