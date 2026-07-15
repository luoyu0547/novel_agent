"""Phase 6 Author Studio — persistence tests."""

import pytest

from app.core.exceptions import NotFound
from app.models.novel import Novel
from app.models.user import User
from app.models.writing import ChapterBrief, ChapterPlan, ContextPackage, WritingRun
from app.services.draft_version_service import DraftVersionService


async def _make_studio_run(db, content: str = "初稿正文"):
    user = User(username="studio_author", hashed_password="x")
    db.add(user)
    await db.flush()
    novel = Novel(title="Studio 测试小说", description="", genre="古风", style_guide="第三人称", user_id=user.id)
    db.add(novel)
    await db.flush()
    plan = ChapterPlan(novel_id=novel.id, position=1)
    db.add(plan)
    await db.flush()
    brief = ChapterBrief(novel_id=novel.id, chapter_plan_id=plan.id)
    db.add(brief)
    await db.flush()
    context = ContextPackage(novel_id=novel.id, chapter_brief_id=brief.id)
    db.add(context)
    await db.flush()
    run = WritingRun(
        novel_id=novel.id, chapter_brief_id=brief.id, context_package_id=context.id,
        status="completed", draft_content=content, word_count=len(content),
        context_snapshot_json={"source_items": [{
            "source_id": "chapter:18:scene:3", "source_type": "chapter_scene",
            "title": "第 18 章 · 第 3 场", "locator": {"chapter_id": 18, "scene_index": 3},
            "preview": "沈砚发现账册异常", "inclusion_reason": "避免越过角色认知",
        }]},
    )
    db.add(run)
    await db.flush()
    version = await DraftVersionService(db, user.id, novel.id).ensure_initial_version(run)
    return user, novel, run, version


@pytest.mark.asyncio
async def test_session_message_and_working_copy_persist(db):
    from app.models.writing_session import DraftWorkingCopy, WritingMessage, WritingSession
    _, novel, completed_run, draft_version = await _make_studio_run(db)

    session = WritingSession(novel_id=novel.id, active_writing_run_id=completed_run.id,
                             title="第十八章草稿", status="active")
    db.add(session)
    await db.flush()
    db.add(WritingMessage(session_id=session.id, role="author", message_type="text",
                          content_json={"text": "让结尾更克制"}, action_status="completed"))
    db.add(DraftWorkingCopy(writing_run_id=completed_run.id, draft_version_id=draft_version.id,
                            title="第十八章", content=draft_version.content,
                            base_revision_sequence=0))
    await db.commit()

    assert session.id is not None
    assert (await db.get(DraftWorkingCopy, completed_run.id)).content == draft_version.content


@pytest.mark.asyncio
async def test_writing_run_session_link_is_optional_for_legacy_rows(db):
    _, _, completed_run, _ = await _make_studio_run(db)
    await db.refresh(completed_run)
    assert completed_run.writing_session_id is None


# ── Task 2: Session lifecycle service tests ────────────────────────────


@pytest.mark.asyncio
async def test_get_or_create_for_run_reuses_one_session(db):
    from app.services.writing_session_service import WritingSessionService

    user, novel, completed_run, _ = await _make_studio_run(db)
    service = WritingSessionService(db, user.id, novel.id)
    first = await service.get_or_create_for_run(completed_run.id)
    second = await service.get_or_create_for_run(completed_run.id)
    assert second.id == first.id


@pytest.mark.asyncio
async def test_session_from_another_user_raises_not_found(db):
    from app.services.writing_session_service import WritingSessionService

    _, novel, completed_run, _ = await _make_studio_run(db)
    other_user = User(username="studio_other", hashed_password="x")
    db.add(other_user)
    await db.flush()
    service = WritingSessionService(db, other_user.id, novel.id)
    with pytest.raises(NotFound):
        await service.get_or_create_for_run(completed_run.id)


@pytest.mark.asyncio
async def test_get_sources_returns_snapshot_items(db):
    from app.schemas.writing_studio import StudioSourceOut
    from app.services.writing_session_service import WritingSessionService

    user, novel, completed_run, _ = await _make_studio_run(db)
    service = WritingSessionService(db, user.id, novel.id)
    sources = await service.get_sources(completed_run.id)
    assert len(sources) == 1
    assert isinstance(sources[0], StudioSourceOut)
    assert sources[0].source_id == "chapter:18:scene:3"
    assert sources[0].source_type == "chapter_scene"
    assert sources[0].title == "第 18 章 · 第 3 场"
    assert sources[0].inclusion_reason == "避免越过角色认知"


@pytest.mark.asyncio
async def test_create_and_list_sessions(db):
    from app.services.writing_session_service import WritingSessionService

    user, novel, _, _ = await _make_studio_run(db)
    service = WritingSessionService(db, user.id, novel.id)
    s1 = await service.create_session(target_chapter_id=None, title="会话 A")
    s2 = await service.create_session(target_chapter_id=None, title="会话 B")
    sessions = await service.list_sessions()
    assert len(sessions) == 2
    assert sessions[0].title in ("会话 A", "会话 B")


@pytest.mark.asyncio
async def test_get_session_raises_not_found_for_wrong_novel(db):
    from app.services.writing_session_service import WritingSessionService

    user, novel, _, _ = await _make_studio_run(db)
    service = WritingSessionService(db, user.id, novel.id)
    s = await service.create_session(target_chapter_id=None, title="test")
    # Create another novel owned by same user
    other_novel = Novel(title="Other", description="", genre="古风", style_guide="", user_id=user.id)
    db.add(other_novel)
    await db.flush()
    other_service = WritingSessionService(db, user.id, other_novel.id)
    with pytest.raises(NotFound):
        await other_service.get_session(s.id)


@pytest.mark.asyncio
async def test_to_workspace_out_includes_messages_and_working_copy(db):
    from app.models.writing_session import DraftWorkingCopy, WritingMessage, WritingSession
    from app.services.writing_session_service import WritingSessionService

    user, novel, completed_run, draft_version = await _make_studio_run(db)
    session = WritingSession(
        novel_id=novel.id, active_writing_run_id=completed_run.id,
        title="工作区测试", status="active",
    )
    db.add(session)
    await db.flush()
    db.add(WritingMessage(
        session_id=session.id, role="author", message_type="text",
        content_json={"text": "请修改结尾"}, action_status="completed",
    ))
    db.add(DraftWorkingCopy(
        writing_run_id=completed_run.id, draft_version_id=draft_version.id,
        title="第十八章", content=draft_version.content,
        base_revision_sequence=0,
    ))
    await db.commit()
    await db.refresh(session)

    service = WritingSessionService(db, user.id, novel.id)
    workspace = await service.to_workspace_out(session)
    assert workspace["session"]["title"] == "工作区测试"
    assert len(workspace["messages"]) == 1
    assert workspace["working_copy"] is not None
    assert workspace["working_copy"]["title"] == "第十八章"
