"""Phase 6 Author Studio — persistence tests."""

import pytest

from app.core.security import create_token
from app.models.draft_version import DraftVersion
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
