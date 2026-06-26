import json

from langchain.tools import tool, ToolRuntime

from app.ai.models import NovelAgentState
from app.models.foreshadowing import Foreshadowing
from app.models.memory import CharacterProfile, WorldSetting
from app.models.plot_fact import PlotFact
from app.core.database import async_session_factory


@tool
async def get_chapter_context(
    novel_id: int,
    chapter_id: int,
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """获取章节全文、已有角色设定、世界观设定、伏笔信息和剧情事实"""
    async with async_session_factory() as db:
        from app.models.novel import Chapter
        result = await db.get(Chapter, chapter_id)
        if not result or result.novel_id != novel_id:
            return "章节不存在"

        chapter = result
        context_parts = [
            f"[章节标题]\n{chapter.title}",
            f"[章节正文]\n{chapter.content}",
        ]

        char_rows = (await db.execute(
            CharacterProfile.__table__.select().where(CharacterProfile.novel_id == novel_id)
        )).fetchall()
        if char_rows:
            parts = ["\n[已有角色]"]
            for c in char_rows:
                parts.append(f"{c['name']}: 身份={c['identity']}, 性格={c['personality']}, 当前状态={c['current_state']}")
            context_parts.append("\n".join(parts))

        setting_rows = (await db.execute(
            WorldSetting.__table__.select().where(WorldSetting.novel_id == novel_id)
        )).fetchall()
        if setting_rows:
            parts = ["\n[已有设定]"]
            for s in setting_rows:
                parts.append(f"{s['title']} ({s['category']}): {s['content']}")
            context_parts.append("\n".join(parts))

        foreshadow_rows = (await db.execute(
            Foreshadowing.__table__.select().where(Foreshadowing.novel_id == novel_id)
        )).fetchall()
        if foreshadow_rows:
            parts = ["\n[已有伏笔]"]
            for f in foreshadow_rows:
                parts.append(f"{f['name']}: {f['description']} (状态={f['status']})")
            context_parts.append("\n".join(parts))

        fact_rows = (await db.execute(
            PlotFact.__table__.select().where(PlotFact.novel_id == novel_id)
        )).fetchall()
        if fact_rows:
            parts = ["\n[已有剧情事实]"]
            for f in fact_rows:
                related = json.dumps(f['related_characters'], ensure_ascii=False)
                parts.append(f"{f['content']} (涉及: {related}, 重要性: {f['importance']})")
            context_parts.append("\n".join(parts))

    return "\n".join(context_parts)
