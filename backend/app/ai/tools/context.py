import json
from sqlalchemy import select

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
        chapter = await db.get(Chapter, chapter_id)
        if not chapter or chapter.novel_id != novel_id:
            return "章节不存在"

        context_parts = [
            f"[章节标题]\n{chapter.title}",
            f"[章节正文]\n{chapter.content}",
        ]

        chars = (await db.execute(
            select(CharacterProfile).where(CharacterProfile.novel_id == novel_id)
        )).scalars().all()
        if chars:
            parts = ["\n[已有角色]"]
            for c in chars:
                parts.append(f"{c.name}: 身份={c.identity}, 性格={c.personality}, 当前状态={c.current_state}")
            context_parts.append("\n".join(parts))

        settings = (await db.execute(
            select(WorldSetting).where(WorldSetting.novel_id == novel_id)
        )).scalars().all()
        if settings:
            parts = ["\n[已有设定]"]
            for s in settings:
                parts.append(f"{s.title} ({s.category}): {s.content}")
            context_parts.append("\n".join(parts))

        foreshadows = (await db.execute(
            select(Foreshadowing).where(Foreshadowing.novel_id == novel_id)
        )).scalars().all()
        if foreshadows:
            parts = ["\n[已有伏笔]"]
            for f in foreshadows:
                parts.append(f"{f.name}: {f.description} (状态={f.status})")
            context_parts.append("\n".join(parts))

        facts = (await db.execute(
            select(PlotFact).where(PlotFact.novel_id == novel_id)
        )).scalars().all()
        if facts:
            parts = ["\n[已有剧情事实]"]
            for f in facts:
                related = json.dumps(f.related_characters, ensure_ascii=False)
                parts.append(f"{f.content} (涉及: {related}, 重要性: {f.importance})")
            context_parts.append("\n".join(parts))

    return "\n".join(context_parts)
