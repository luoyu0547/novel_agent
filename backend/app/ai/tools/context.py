import json
from sqlalchemy import select

from langchain.tools import tool, ToolRuntime

from app.ai.models import NovelAgentState
from app.models.foreshadowing import Foreshadowing
from app.models.memory import CharacterProfile, WorldSetting
from app.models.plot_fact import PlotFact
from app.core.database import async_session_factory


_MAX_SECTION_CHARS = 5000
_MAX_FIELD_CHARS = 500


def _clip(value: object, limit: int = _MAX_FIELD_CHARS) -> str:
    text = str(value or "")
    return text if len(text) <= limit else f"{text[:limit]}…"


def _bounded_section(header: str, lines: list[str]) -> str:
    section = "\n".join([header, *lines])
    if len(section) <= _MAX_SECTION_CHARS:
        return section
    return (
        f"{section[:_MAX_SECTION_CHARS]}\n"
        "[该类记忆较多，其余内容已省略；相关资料由检索结果补充]"
    )


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
            lines = [
                f"{_clip(c.name, 120)}: 身份={_clip(c.identity)}, "
                f"性格={_clip(c.personality)}, 当前状态={_clip(c.current_state)}"
                for c in chars
            ]
            context_parts.append(_bounded_section("\n[已有角色]", lines))

        settings = (await db.execute(
            select(WorldSetting).where(WorldSetting.novel_id == novel_id)
        )).scalars().all()
        if settings:
            lines = [
                f"{_clip(s.title, 160)} ({_clip(s.category, 80)}): {_clip(s.content)}"
                for s in settings
            ]
            context_parts.append(_bounded_section("\n[已有设定]", lines))

        foreshadows = (await db.execute(
            select(Foreshadowing).where(Foreshadowing.novel_id == novel_id)
        )).scalars().all()
        if foreshadows:
            lines = [
                f"{_clip(f.name, 160)}: {_clip(f.description)} (状态={_clip(f.status, 80)})"
                for f in foreshadows
            ]
            context_parts.append(_bounded_section("\n[已有伏笔]", lines))

        facts = (await db.execute(
            select(PlotFact).where(PlotFact.novel_id == novel_id)
        )).scalars().all()
        if facts:
            lines = [
                f"{_clip(f.content)} (涉及: {_clip(json.dumps(f.related_characters, ensure_ascii=False))}, "
                f"重要性: {_clip(f.importance, 80)})"
                for f in facts
            ]
            context_parts.append(_bounded_section("\n[已有剧情事实]", lines))

        state = getattr(runtime, "state", {}) or {}
        user_id = state.get("user_id", 0) if isinstance(state, dict) else 0
        if user_id:
            from app.retrieval.contracts import RetrievalRequest
            from app.retrieval.runtime import get_retrieval_provider

            provider = get_retrieval_provider()
            if provider:
                retrieval = await provider.retrieve(
                    RetrievalRequest(
                        user_id=user_id,
                        novel_id=novel_id,
                        query=f"{chapter.title}\n{chapter.content[:6000]}",
                        target_chapter_id=chapter_id,
                    )
                )
                if retrieval.writer_items:
                    lines = [
                        f"{_clip(item.get('title'), 160)}: "
                        f"{_clip(item.get('text') or item.get('preview'))}"
                        for item in retrieval.writer_items
                    ]
                    context_parts.append(_bounded_section("\n[检索到的相关资料]", lines))

    return "\n".join(context_parts)
