"""Phase 4 辅助修订——DraftVersion 生命周期服务。

提供版本创建、手动修订保存、版本恢复、修订拒绝等业务逻辑。
入参直接使用原始类型而非 Pydantic schema，由路由层做 schema 校验。
"""

import datetime
import hashlib
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, NotFound
from app.models.draft_version import DraftVersion
from app.models.novel import Chapter, Novel
from app.models.plot_planning import DraftRevision
from app.models.writing import WritingRun
from app.repositories.draft_version_repo import DraftVersionRepo

logger = logging.getLogger("novel_agent.draft_version")


class DraftVersionService:
    """DraftVersion 生命周期服务。

    职责：
    - 确保 WritingRun 有初始版本 (v1)。
    - 管理显式版本创建 (vN+1)。
    - 保存手动修订和版本恢复。
    - 拒绝修订和运行标记。
    """

    def __init__(self, db: AsyncSession, user_id: int, novel_id: int):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.repo = DraftVersionRepo(db)

    # ── Private helpers ──────────────────────────────────────────────

    async def _ensure_owned_novel(self) -> Novel:
        result = await self.db.execute(
            select(Novel).where(Novel.id == self.novel_id)
        )
        novel = result.scalar_one_or_none()
        if not novel or novel.user_id != self.user_id:
            raise NotFound("小说不存在")
        return novel

    async def _get_owned_run(self, run_id: int) -> WritingRun:
        """获取 run 并验证归属当前 novel。"""
        result = await self.db.execute(
            select(WritingRun).where(
                WritingRun.id == run_id,
                WritingRun.novel_id == self.novel_id,
            )
        )
        run = result.scalar_one_or_none()
        if not run:
            raise NotFound("写作运行不存在")
        return run

    async def _get_current_mutable_version(self, run: WritingRun) -> DraftVersion:
        """获取 run 的当前 draft 版本。"""
        version = await self.repo.get_current(run.id)
        if not version:
            raise BadRequest("当前没有可编辑的草稿版本")
        return version

    async def _ensure_target_unlocked(self, run: WritingRun) -> None:
        """检查目标章节是否已发布（locked）。"""
        if not run.target_chapter_id:
            return
        chapter = await self.db.get(Chapter, run.target_chapter_id)
        if chapter and chapter.status == "locked":
            raise BadRequest("目标章节已发布，不可修改")

    @staticmethod
    def _count_words(content: str) -> int:
        return len(content)

    @staticmethod
    def _hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _single_patch(base: str, candidate: str, reason: str) -> list[dict]:
        """计算 base → candidate 的单一补丁（最长公共前后缀）。"""
        if base == candidate:
            return []
        # longest common prefix
        prefix_len = 0
        while (
            prefix_len < len(base)
            and prefix_len < len(candidate)
            and base[prefix_len] == candidate[prefix_len]
        ):
            prefix_len += 1
        # longest common suffix (starting after prefix)
        suffix_len_base = len(base) - 1
        suffix_len_candidate = len(candidate) - 1
        while (
            suffix_len_base >= prefix_len
            and suffix_len_candidate >= prefix_len
            and base[suffix_len_base] == candidate[suffix_len_candidate]
        ):
            suffix_len_base -= 1
            suffix_len_candidate -= 1
        return [
            {
                "start_offset": prefix_len,
                "end_offset": suffix_len_base + 1,
                "original_text": base[prefix_len : suffix_len_base + 1],
                "replacement_text": candidate[
                    prefix_len : suffix_len_candidate + 1
                ],
                "reason": reason,
            }
        ]

    def _sync_run(self, run: WritingRun, version: DraftVersion) -> None:
        """将 version 的内容同步到 run。"""
        run.draft_content = version.content
        run.word_count = version.word_count
        run.updated_at = datetime.datetime.now()

    # ── Public API ───────────────────────────────────────────────────

    async def ensure_initial_version(
        self, run: WritingRun, title: str = "首次生成"
    ) -> DraftVersion:
        """确保 run 有初始版本。

        如果已经有 draft 状态版本则直接返回（幂等）。
        否则以 run 的 draft_content 创建 v1。
        不创建 DraftRevision（生成内部的重写不产生版本修订）。
        """
        existing = await self.repo.get_current(run.id)
        if existing:
            return existing

        if not run.draft_content:
            raise BadRequest("写作运行没有草稿内容")

        version = await self.repo.create(
            self.novel_id,
            {
                "writing_run_id": run.id,
                "chapter_id": run.target_chapter_id,
                "version": 1,
                "title": title,
                "content": run.draft_content,
                "word_count": self._count_words(run.draft_content),
                "change_reason": title,
                "status": "draft",
                "revision_sequence": 0,
            },
        )
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def list_versions(self, run_id: int) -> list[DraftVersion]:
        """列出 run 的所有版本，按 version DESC 排序。"""
        await self._get_owned_run(run_id)
        return await self.repo.list_by_run(run_id)

    async def get_version(self, version_id: int) -> DraftVersion:
        """获取指定版本（含归属校验）。"""
        version = await self.repo.get(version_id, self.novel_id)
        if not version:
            raise NotFound("版本不存在")
        return version

    async def create_new_version(
        self,
        run_id: int,
        based_on_version_id: int,
        change_reason: str,
    ) -> DraftVersion:
        """创建新版本 (vN+1)。

        Steps:
        1. 验证 run 未被接受/丢弃。
        2. 验证目标章节未锁定。
        3. 验证源版本属于该 run 和 novel。
        4. 验证恰好有一个当前 draft 版本。
        5. 归档当前 draft 版本。
        6. 创建 max(version)+1 版本，同步 run 内容/字数。
        """
        if not change_reason:
            raise BadRequest("变更原因不能为空")

        run = await self._get_owned_run(run_id)

        if run.status in ("accepted", "discarded"):
            raise BadRequest("写作运行已接受或丢弃，不可创建新版本")

        await self._ensure_target_unlocked(run)

        # 验证源版本
        source_version = await self.repo.get(based_on_version_id, self.novel_id)
        if not source_version:
            raise NotFound("源版本不存在")
        if source_version.writing_run_id != run.id:
            raise BadRequest("源版本不属于该写作运行")

        # 获取当前 draft 版本并归档
        current = await self.repo.get_current(run.id)
        if not current:
            raise BadRequest("当前没有草稿版本可归档")

        current.status = "archived"
        current.updated_at = datetime.datetime.now()

        # 计算下一个版本号并创建
        next_version = await self.repo.next_version_number(run.id)

        try:
            new_version = await self.repo.create(
                self.novel_id,
                {
                    "writing_run_id": run.id,
                    "chapter_id": run.target_chapter_id,
                    "based_on_version_id": based_on_version_id,
                    "version": next_version,
                    "title": f"v{next_version}",
                    "content": source_version.content,
                    "word_count": source_version.word_count,
                    "change_reason": change_reason,
                    "status": "draft",
                    "revision_sequence": 0,
                },
            )

            self._sync_run(run, new_version)
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise BadRequest("并发冲突，请刷新后重试")

        await self.db.refresh(new_version)
        return new_version

    async def save_manual_revision(
        self,
        run_id: int,
        content: str,
        change_reason: str,
        base_revision_sequence: int,
    ) -> tuple[DraftVersion, DraftRevision]:
        """保存手动修订到当前 draft 版本。

        创建一条 source_type=manual_edit 且 status=applied 的 DraftRevision，
        同时更新 DraftVersion 的 content/word_count/revision_sequence。
        """
        if not change_reason:
            raise BadRequest("变更原因不能为空")

        run = await self._get_owned_run(run_id)
        await self._ensure_target_unlocked(run)

        version = await self._get_current_mutable_version(run)

        # 正文必须变化
        if content == version.content:
            raise BadRequest("正文没有变化")

        # 并发保护：base_revision_sequence 必须匹配当前版本
        if base_revision_sequence != version.revision_sequence:
            raise BadRequest("基础修订序列已过期，请刷新后重试")

        patches = self._single_patch(version.content, content, change_reason)
        new_revision_sequence = version.revision_sequence + 1

        revision = await self.repo.create_revision(
            self.novel_id,
            {
                "writing_run_id": run.id,
                "draft_version_id": version.id,
                "sequence": new_revision_sequence,
                "source_type": "manual_edit",
                "source_id": None,
                "base_revision_sequence": base_revision_sequence,
                "base_content_hash": self._hash_content(version.content),
                "base_content": version.content,
                "candidate_content": content,
                "patches_json": patches,
                "diff_json": {"old": version.content, "new": content},
                "scope_json": {"type": "manual"},
                "reason": change_reason,
                "status": "applied",
            },
        )

        word_count = self._count_words(content)
        version.content = content
        version.word_count = word_count
        version.revision_sequence = new_revision_sequence
        version.updated_at = datetime.datetime.now()
        self._sync_run(run, version)

        await self.db.commit()
        await self.db.refresh(version)
        await self.db.refresh(revision)
        return version, revision

    async def restore_into_current(
        self,
        source_version_id: int,
        base_revision_sequence: int,
        change_reason: str,
    ) -> tuple[DraftVersion, DraftRevision]:
        """恢复到历史版本内容。

        在当前 draft 版本上创建一条 source_type=restore 的 DraftRevision，
        将 content 替换为源版本内容，不创建新 DraftVersion。
        """
        if not change_reason:
            raise BadRequest("变更原因不能为空")

        source_version = await self.repo.get(source_version_id, self.novel_id)
        if not source_version:
            raise NotFound("源版本不存在")
        if source_version.writing_run_id is None:
            raise BadRequest("源版本未关联写作运行")

        # 在获取当前版本之前提取源内容（二者可能为同一 ORM 实例）
        source_content = source_version.content
        source_word_count = source_version.word_count

        run = await self._get_owned_run(source_version.writing_run_id)
        await self._ensure_target_unlocked(run)

        version = await self._get_current_mutable_version(run)

        if base_revision_sequence != version.revision_sequence:
            raise BadRequest("基础修订序列已过期，请刷新后重试")

        patches = self._single_patch(
            version.content, source_content, change_reason
        )
        new_revision_sequence = version.revision_sequence + 1

        revision = await self.repo.create_revision(
            self.novel_id,
            {
                "writing_run_id": run.id,
                "draft_version_id": version.id,
                "sequence": new_revision_sequence,
                "source_type": "restore",
                "source_id": source_version_id,
                "base_revision_sequence": base_revision_sequence,
                "base_content_hash": self._hash_content(version.content),
                "base_content": version.content,
                "candidate_content": source_content,
                "patches_json": patches,
                "diff_json": {
                    "old": version.content,
                    "new": source_content,
                },
                "scope_json": {
                    "type": "restore",
                    "source_version_id": source_version_id,
                },
                "reason": change_reason,
                "status": "applied",
            },
        )

        version.content = source_content
        version.word_count = source_word_count
        version.revision_sequence = new_revision_sequence
        version.updated_at = datetime.datetime.now()
        self._sync_run(run, version)

        await self.db.commit()
        await self.db.refresh(version)
        await self.db.refresh(revision)
        return version, revision

    async def reject_revision(self, revision_id: int) -> DraftRevision:
        """拒绝一个候选修订。"""
        revision = await self.repo.get_revision(revision_id, self.novel_id)
        if not revision:
            raise NotFound("修订不存在")
        if revision.status != "candidate":
            raise BadRequest("只能拒绝候选状态的修订")

        revision.status = "rejected"
        revision.updated_at = datetime.datetime.now()
        await self.db.commit()
        await self.db.refresh(revision)
        return revision

    async def mark_run_rejected(self, run: WritingRun) -> Optional[DraftVersion]:
        """标记 run 的当前 draft 版本为 rejected。

        如果 run 没有当前 draft 版本则返回 None。
        """
        version = await self.repo.get_current(run.id)
        if not version:
            return None

        version.status = "rejected"
        version.updated_at = datetime.datetime.now()
        await self.db.commit()
        await self.db.refresh(version)
        return version
