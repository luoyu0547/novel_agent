"""Canonical source builder for the retrieval subsystem.

Collects locked chapters, confirmed canonical memories (characters, world
settings, plot facts, foreshadowings) from the database and produces a list
of :class:`RetrievalSource` records ready for embedding and indexing.

Only locked chapters and confirmed canonical memories are included — never
draft chapters, WorkingCopy content, or unconfirmed PendingMemory entries.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.foreshadowing import Foreshadowing
from app.models.memory import CharacterProfile, WorldSetting
from app.models.novel import Chapter
from app.models.plot_fact import PlotFact

# ---------------------------------------------------------------------------
# Scene chunking constants
# ---------------------------------------------------------------------------

_MAX_SCENE_CHARS = 700  # Chinese characters per scene chunk
_CARRY_OVER_CHARS = 120  # Carry final N chars into next chunk


# ---------------------------------------------------------------------------
# RetrievalSource record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetrievalSource:
    """A single canonical source record produced by the builder.

    Attributes
    ----------
    source_id:
        Stable identifier following the spec format, e.g.
        ``chapter:3:summary``, ``foreshadowing:7:signal``.
    source_type:
        Category label: ``chapter_summary``, ``chapter_scene``,
        ``character_profile``, ``plot_fact``, ``world_setting``,
        ``foreshadowing_signal``, ``foreshadowing_guard``.
    source_record_id:
        The database primary key of the originating record.
    chapter_id:
        The chapter ID if the source is chapter-scoped, else ``None``.
    title:
        Human-readable label for display / debugging.
    text:
        The full text content to be embedded.
    preview:
        A short preview (first ~100 chars) for search result display.
    visibility:
        ``"default"`` for public sources, ``"guard"`` for foreshadowing
        guard records that contain hidden truths.
    locator:
        JSON-serializable dict for frontend navigation.
    content_hash:
        SHA-256 hex digest of the normalized text.
    tenant_key:
        ``"{user_id}:{novel_id}"`` for multi-tenant scoping.
    point_id:
        Deterministic UUID5 derived from tenant_key + source_id + hash + "v1".
    """

    source_id: str
    source_type: str
    source_record_id: int
    chapter_id: int | None
    title: str
    text: str
    preview: str
    visibility: str
    locator: dict
    content_hash: str
    tenant_key: str
    point_id: str
    importance: str = "minor"
    index_version: str = "v1"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _normalize_text(text: str) -> str:
    """Normalize text for consistent hashing: strip outer whitespace,
    collapse internal whitespace runs, normalize line endings."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _content_hash(text: str) -> str:
    """SHA-256 hex digest of the normalized text encoded as UTF-8."""
    normalized = _normalize_text(text)
    return hashlib.sha256(normalized.encode()).hexdigest()


def _point_id(tenant_key: str, source_id: str, content_hash: str) -> str:
    """Deterministic UUID5 from tenant_key + source_id + hash + version tag."""
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
    key = f"{tenant_key}:{source_id}:{content_hash}:v1"
    return str(uuid.uuid5(namespace, key))


def _preview(text: str, max_len: int = 100) -> str:
    """Return a short preview of the text."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def _cjk_count(text: str) -> int:
    """Count Chinese characters in text."""
    return sum(1 for ch in text if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿")


def _split_scenes(content: str) -> list[str]:
    """Split chapter content by blank-line boundaries into scene chunks.

    Each blank-line-separated block is a scene.  If a single block exceeds
    :data:`_MAX_SCENE_CHARS` Chinese characters, it is further split and
    the final :data:`_CARRY_OVER_CHARS` characters are carried into the
    next chunk for context continuity.

    Single paragraphs that exceed ``_MAX_SCENE_CHARS`` are split at the
    700-char boundary with 120-char carry-over, continuing until all
    chunks are under the limit.
    """
    # Split on one or more blank lines — each block is a scene
    blocks = re.split(r"\n\s*\n", content)
    blocks = [b.strip() for b in blocks if b.strip()]

    if not blocks:
        return []

    chunks: list[str] = []

    for block in blocks:
        # Count Chinese characters in this block
        if _cjk_count(block) <= _MAX_SCENE_CHARS:
            # Block fits in a single chunk
            chunks.append(block)
            continue

        # Block is too long — split by paragraphs within the block
        paragraphs = [p.strip() for p in block.split("\n") if p.strip()]
        carry = ""
        current = ""

        for para in paragraphs:
            candidate = (carry + para) if carry else ((current + "\n" + para) if current else para)
            candidate = candidate.strip()
            cjk = _cjk_count(candidate)

            if cjk <= _MAX_SCENE_CHARS:
                # Fits — absorb into current
                current = candidate
                carry = ""
            elif not current:
                # Single paragraph exceeds limit — split at boundary with carry-over
                # Keep splitting the paragraph until the remainder fits
                remaining = candidate
                while _cjk_count(remaining) > _MAX_SCENE_CHARS:
                    # Find the split position at _MAX_SCENE_CHARS CJK chars
                    cjk_seen = 0
                    split_pos = 0
                    for i, ch in enumerate(remaining):
                        if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿":
                            cjk_seen += 1
                        if cjk_seen == _MAX_SCENE_CHARS:
                            split_pos = i + 1
                            break
                    # Emit the chunk up to split_pos
                    chunks.append(remaining[:split_pos])
                    # Carry the last _CARRY_OVER_CHARS chars into the next chunk
                    carry_start = max(0, split_pos - _CARRY_OVER_CHARS)
                    remaining = remaining[carry_start:]
                # Whatever remains fits in one chunk
                current = remaining
                carry = ""
            else:
                # Current + para exceeds — emit current, start new with carry + para
                chunks.append(current)
                carry = current[-_CARRY_OVER_CHARS:]
                current = (carry + "\n" + para).strip() if "\n" in current else (carry + para).strip()
                carry = ""
                # If the combined carry+para still exceeds, split the para portion
                if _cjk_count(current) > _MAX_SCENE_CHARS:
                    chunks.append(current)
                    carry = current[-_CARRY_OVER_CHARS:]
                    current = ""
                    carry = ""

        if current:
            chunks.append(current)

    return chunks


# ---------------------------------------------------------------------------
# CanonicalSourceBuilder
# ---------------------------------------------------------------------------


class CanonicalSourceBuilder:
    """Builds the list of canonical :class:`RetrievalSource` records for a novel.

    Parameters
    ----------
    db:
        Async database session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def build(self, novel_id: int, user_id: int) -> list[RetrievalSource]:
        """Collect all canonical sources for the given novel.

        Only locked chapters and confirmed canonical memories are included.
        """
        tenant_key = f"{user_id}:{novel_id}"
        sources: list[RetrievalSource] = []

        # -- Locked chapters (summaries + scene chunks) ----------------------
        result = await self._db.execute(
            select(Chapter).where(
                Chapter.novel_id == novel_id,
                Chapter.status == "locked",
            )
        )
        locked_chapters: Sequence[Chapter] = result.scalars().all()

        for chapter in locked_chapters:
            # Chapter summary source
            if chapter.summary:
                src = self._make_source(
                    source_id=f"chapter:{chapter.id}:summary",
                    source_type="chapter_summary",
                    record_id=chapter.id,
                    chapter_id=chapter.id,
                    title=chapter.title,
                    text=chapter.summary,
                    visibility="default",
                    locator={"chapter_id": chapter.id, "type": "summary"},
                    tenant_key=tenant_key,
                )
                sources.append(src)

            # Scene chunks from chapter content
            scenes = _split_scenes(chapter.content)
            for idx, scene_text in enumerate(scenes):
                src = self._make_source(
                    source_id=f"chapter:{chapter.id}:scene:{idx}",
                    source_type="chapter_scene",
                    record_id=chapter.id,
                    chapter_id=chapter.id,
                    title=f"{chapter.title} · 场景{idx + 1}",
                    text=scene_text,
                    visibility="default",
                    locator={"chapter_id": chapter.id, "type": "scene", "scene_index": idx},
                    tenant_key=tenant_key,
                )
                sources.append(src)

        # -- Characters -------------------------------------------------------
        result = await self._db.execute(
            select(CharacterProfile).where(CharacterProfile.novel_id == novel_id)
        )
        characters: Sequence[CharacterProfile] = result.scalars().all()

        for char in characters:
            parts = [f"姓名：{char.name}"]
            if char.story_role:
                parts.append(f"角色定位：{char.story_role}")
            if char.identity:
                parts.append(f"身份：{char.identity}")
            if char.personality:
                parts.append(f"性格：{char.personality}")
            if char.motivation:
                parts.append(f"动机：{char.motivation}")
            if char.speech_style:
                parts.append(f"语言风格：{char.speech_style}")
            if char.current_state:
                parts.append(f"当前状态：{char.current_state}")
            if char.behavior_rules:
                rules = "；".join(char.behavior_rules) if isinstance(char.behavior_rules, list) else str(char.behavior_rules)
                parts.append(f"行为准则：{rules}")

            text = "\n".join(parts)
            src = self._make_source(
                source_id=f"character_profile:{char.id}",
                source_type="character_profile",
                record_id=char.id,
                chapter_id=None,
                title=char.name,
                text=text,
                visibility="default",
                locator={"character_id": char.id},
                tenant_key=tenant_key,
            )
            sources.append(src)

        # -- Plot facts -------------------------------------------------------
        result = await self._db.execute(
            select(PlotFact).where(PlotFact.novel_id == novel_id)
        )
        facts: Sequence[PlotFact] = result.scalars().all()

        for fact in facts:
            parts = [f"类型：{fact.fact_type}"]
            parts.append(f"内容：{fact.content}")
            parts.append(f"重要度：{fact.importance}")
            if fact.related_characters:
                chars = "、".join(fact.related_characters) if isinstance(fact.related_characters, list) else str(fact.related_characters)
                parts.append(f"相关角色：{chars}")

            text = "\n".join(parts)
            src = self._make_source(
                source_id=f"plot_fact:{fact.id}",
                source_type="plot_fact",
                record_id=fact.id,
                chapter_id=fact.chapter_id,
                title=f"情节事实：{fact.content[:30]}",
                text=text,
                visibility="default",
                locator={"plot_fact_id": fact.id, "chapter_id": fact.chapter_id},
                tenant_key=tenant_key,
                importance=fact.importance,
            )
            sources.append(src)

        # -- World settings ---------------------------------------------------
        result = await self._db.execute(
            select(WorldSetting).where(WorldSetting.novel_id == novel_id)
        )
        settings: Sequence[WorldSetting] = result.scalars().all()

        for setting in settings:
            parts = [f"类别：{setting.category}"]
            parts.append(f"标题：{setting.title}")
            parts.append(f"内容：{setting.content}")

            text = "\n".join(parts)
            src = self._make_source(
                source_id=f"world_setting:{setting.id}",
                source_type="world_setting",
                record_id=setting.id,
                chapter_id=None,
                title=setting.title,
                text=text,
                visibility="default",
                locator={"world_setting_id": setting.id},
                tenant_key=tenant_key,
            )
            sources.append(src)

        # -- Foreshadowings (signal + guard) ----------------------------------
        result = await self._db.execute(
            select(Foreshadowing).where(Foreshadowing.novel_id == novel_id)
        )
        foreshadowings: Sequence[Foreshadowing] = result.scalars().all()

        for fs in foreshadowings:
            # Signal: name/description/status only — NO hidden_truth
            signal_parts = [f"名称：{fs.name}"]
            signal_parts.append(f"描述：{fs.description}")
            signal_parts.append(f"状态：{fs.status}")
            signal_text = "\n".join(signal_parts)

            sources.append(self._make_source(
                source_id=f"foreshadowing:{fs.id}:signal",
                source_type="foreshadowing_signal",
                record_id=fs.id,
                chapter_id=fs.planted_chapter_id,
                title=f"伏笔信号：{fs.name}",
                text=signal_text,
                visibility="default",
                locator={"foreshadowing_id": fs.id, "type": "signal", "chapter_id": fs.planted_chapter_id},
                tenant_key=tenant_key,
            ))

            # Guard: may contain hidden_truth and risk_warning
            guard_parts = [f"名称：{fs.name}"]
            guard_parts.append(f"描述：{fs.description}")
            guard_parts.append(f"状态：{fs.status}")
            if fs.hidden_truth:
                guard_parts.append(f"隐藏真相：{fs.hidden_truth}")
            if fs.risk_warning:
                guard_parts.append(f"风险提示：{fs.risk_warning}")
            if fs.expected_reveal_chapter_id:
                guard_parts.append(f"预计揭示章节：{fs.expected_reveal_chapter_id}")
            guard_text = "\n".join(guard_parts)

            sources.append(self._make_source(
                source_id=f"foreshadowing:{fs.id}:guard",
                source_type="foreshadowing_guard",
                record_id=fs.id,
                chapter_id=fs.planted_chapter_id,
                title=f"伏笔守护：{fs.name}",
                text=guard_text,
                visibility="guard",
                locator={"foreshadowing_id": fs.id, "type": "guard", "chapter_id": fs.planted_chapter_id},
                tenant_key=tenant_key,
            ))

        return sources

    # -- Private helpers ------------------------------------------------------

    @staticmethod
    def _make_source(
        *,
        source_id: str,
        source_type: str,
        record_id: int,
        chapter_id: int | None,
        title: str,
        text: str,
        visibility: str,
        locator: dict,
        tenant_key: str,
        importance: str = "minor",
    ) -> RetrievalSource:
        """Create a :class:`RetrievalSource` with computed hash and point_id."""
        chash = _content_hash(text)
        return RetrievalSource(
            source_id=source_id,
            source_type=source_type,
            source_record_id=record_id,
            chapter_id=chapter_id,
            title=title,
            text=text,
            preview=_preview(text),
            visibility=visibility,
            locator=locator,
            content_hash=chash,
            tenant_key=tenant_key,
            point_id=_point_id(tenant_key, source_id, chash),
            importance=importance,
        )
