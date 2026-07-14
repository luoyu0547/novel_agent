"""Phase 4 辅助修订——修改服务。

ModificationService 管理修复选项生成、候选修订创建和问题忽略。
核心保证：create_revision 不改变当前正文或问题状态，仅创建 candidate DraftRevision。
"""

import hashlib
import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.modification import (
    BaseModificationAgent,
    DeepSeekModificationAgent,
    ModificationOutput,
    RepairOption,
    RepairOptionsOutput,
    RevisionPatch,
)
from app.core.exceptions import BadRequest, NotFound
from app.models.draft_version import DraftVersion
from app.models.novel import Novel
from app.models.plot_planning import DraftRevision
from app.models.quality_gate import ReviewIssue
from app.models.writing import WritingRun
from app.repositories.draft_version_repo import DraftVersionRepo
from app.repositories.quality_gate_repo import ReviewIssueRepo

logger = logging.getLogger("novel_agent.modification")

# 300-character context window on each side of the issue location
_SCOPE_WINDOW = 300


def apply_patches(base: str, patches: list[RevisionPatch]) -> str:
    """将补丁列表应用到基础文本，返回修改后的文本。

    补丁按 start_offset 排序后依次应用。重叠或反转的偏移量、
    不匹配的 original_text 均会抛出 BadRequest。
    """
    ordered = sorted(patches, key=lambda item: item.start_offset)
    cursor = 0
    pieces: list[str] = []
    for patch in ordered:
        if patch.start_offset < cursor or patch.end_offset < patch.start_offset:
            raise BadRequest("修改片段重叠或范围无效")
        if base[patch.start_offset : patch.end_offset] != patch.original_text:
            raise BadRequest("修改片段与当前正文不匹配")
        pieces.append(base[cursor : patch.start_offset])
        pieces.append(patch.replacement_text)
        cursor = patch.end_offset
    pieces.append(base[cursor:])
    return "".join(pieces)


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _locate_issue_window(base: str, location: str) -> tuple[int, int]:
    """在 base 中定位 issue.location 的上下文窗口。

    返回 (window_start, window_end)，即 location 出现位置前后各
    _SCOPE_WINDOW 字符的范围。如果 location 未找到，返回 (0, len(base))。
    """
    idx = base.find(location)
    if idx == -1:
        return 0, len(base)
    window_start = max(0, idx - _SCOPE_WINDOW)
    window_end = min(len(base), idx + len(location) + _SCOPE_WINDOW)
    return window_start, window_end


class ModificationService:
    """修改服务：修复选项生成、候选修订创建、问题忽略。"""

    def __init__(
        self,
        db: AsyncSession,
        user_id: int,
        novel_id: int,
        modification_agent: Optional[BaseModificationAgent] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.novel_id = novel_id
        self.agent = modification_agent or DeepSeekModificationAgent()
        self.issue_repo = ReviewIssueRepo(db)
        self.version_repo = DraftVersionRepo(db)

    # ── Private helpers ──────────────────────────────────────────────

    async def _ensure_owned_novel(self) -> Novel:
        result = await self.db.execute(
            select(Novel).where(Novel.id == self.novel_id)
        )
        novel = result.scalar_one_or_none()
        if not novel or novel.user_id != self.user_id:
            raise NotFound("小说不存在")
        return novel

    async def _get_owned_open_issue(self, issue_id: int) -> ReviewIssue:
        """获取归属当前 novel 的 open 状态问题。"""
        issue = await self.issue_repo.get(issue_id, self.novel_id)
        if not issue:
            raise NotFound("审阅问题不存在")
        if issue.status != "open":
            raise BadRequest("只能对 open 状态的问题生成修复选项")
        return issue

    async def _get_current_mutable_version(
        self, writing_run_id: int
    ) -> DraftVersion:
        """获取写作运行的当前 draft 版本。"""
        version = await self.version_repo.get_current(writing_run_id)
        if not version:
            raise BadRequest("当前没有可编辑的草稿版本")
        return version

    def _build_context(
        self,
        issue: ReviewIssue,
        version: DraftVersion,
        selected_option: dict | None = None,
        custom_intent: str | None = None,
    ) -> dict:
        """构建代理调用上下文字典。"""
        context: dict = {
            "current_content": version.content,
            "issue": {
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "location": issue.location,
                "description": issue.description,
                "related_memory": issue.related_memory or "",
                "suggestion": issue.suggestion,
            },
        }

        if selected_option is not None:
            context["selected_option"] = selected_option
        if custom_intent is not None:
            context["custom_intent"] = custom_intent

        # 可选上下文：从 writing_run 获取
        if issue.writing_run_id:
            # 这些字段在调用前由 service 填充
            context.setdefault("chapter_brief", {})
            context.setdefault("context_snapshot", {})
            context.setdefault("author_foundation", {})
            context.setdefault("plot_plan", {})
            context.setdefault("published_facts", [])

        return context

    def _validate_scope(
        self,
        base: str,
        location: str,
        output: ModificationOutput,
    ) -> None:
        """验证补丁范围是否在问题位置的 300 字窗口内。

        如果任何补丁超出窗口，要求 expanded_scope=true 且有 reason。
        """
        window_start, window_end = _locate_issue_window(base, location)

        for patch in output.patches:
            if patch.start_offset < window_start or patch.end_offset > window_end:
                if not output.expanded_scope:
                    raise BadRequest("修改范围超出问题上下文窗口，但未声明 expanded_scope")
                if not output.expanded_scope_reason:
                    raise BadRequest("修改范围超出问题上下文窗口，但未提供 expanded_scope_reason")
                # 只要有一个 patch 超出且已声明，就通过
                return

    # ── Public API ───────────────────────────────────────────────────

    async def generate_options(self, issue_id: int) -> list[RepairOption]:
        """为 open 状态的审阅问题生成修复选项。

        Steps:
        1. 获取归属的 open 问题
        2. 获取当前可编辑版本
        3. 构建上下文
        4. 调用代理生成选项
        5. 存储选项 JSON 到问题
        6. 返回选项列表
        """
        await self._ensure_owned_novel()
        issue = await self._get_owned_open_issue(issue_id)

        if not issue.writing_run_id:
            raise BadRequest("审阅问题未关联写作运行")

        version = await self._get_current_mutable_version(issue.writing_run_id)
        context = self._build_context(issue, version)

        output = await self.agent.generate_options(context)

        # 存储选项 JSON
        options_data = [opt.model_dump() for opt in output.options]
        await self.issue_repo.update(
            issue,
            {
                "repair_options_json": options_data,
            },
        )
        await self.db.commit()
        await self.db.refresh(issue)

        return output.options

    async def create_revision(
        self,
        issue_id: int,
        option_index: int | None = None,
        custom_intent: str | None = None,
    ) -> DraftRevision:
        """为审阅问题创建候选修订。

        核心保证：不改变当前正文或问题状态，仅创建 candidate DraftRevision。

        Steps:
        1. 验证归属的 open 问题和当前可编辑版本
        2. 解析选中的选项或自定义意图
        3. 调用代理生成修订
        4. 通过 apply_patches 验证补丁
        5. 验证范围（300 字窗口）
        6. 创建 candidate DraftRevision
        7. 提交但不改变当前内容或问题状态
        """
        await self._ensure_owned_novel()
        issue = await self._get_owned_open_issue(issue_id)

        if not issue.writing_run_id:
            raise BadRequest("审阅问题未关联写作运行")

        version = await self._get_current_mutable_version(issue.writing_run_id)

        # 解析选中的选项或自定义意图
        selected_option: dict | None = None
        if option_index is not None:
            if not issue.repair_options_json:
                raise BadRequest("该问题尚未生成修复选项")
            if option_index < 0 or option_index >= len(issue.repair_options_json):
                raise BadRequest("选项索引无效")
            selected_option = issue.repair_options_json[option_index]
        elif custom_intent is not None:
            if not custom_intent.strip():
                raise BadRequest("自定义意图不能为空")
        else:
            raise BadRequest("必须提供 option_index 或 custom_intent")

        context = self._build_context(
            issue, version, selected_option=selected_option, custom_intent=custom_intent
        )

        # 调用代理
        output = await self.agent.create_revision(context)

        # 验证补丁：apply_patches 必须能重建 candidate_content
        try:
            reconstructed = apply_patches(version.content, output.patches)
        except BadRequest:
            logger.warning("补丁验证失败：重叠或范围无效")
            raise

        if reconstructed != output.candidate_content:
            raise BadRequest("候选内容与补丁重建结果不一致")

        # 验证范围
        self._validate_scope(version.content, issue.location, output)

        # 创建 candidate DraftRevision
        revision = await self.version_repo.create_revision(
            self.novel_id,
            {
                "writing_run_id": issue.writing_run_id,
                "draft_version_id": version.id,
                "sequence": 0,
                "source_type": "review_issue",
                "source_id": issue.id,
                "base_revision_sequence": version.revision_sequence,
                "base_content_hash": _hash_content(version.content),
                "base_content": version.content,
                "candidate_content": output.candidate_content,
                "patches_json": [p.model_dump() for p in output.patches],
                "scope_json": output.scope,
                "diff_json": output.diff,
                "reason": output.change_reason,
                "expanded_scope": output.expanded_scope,
                "expanded_scope_reason": output.expanded_scope_reason,
                "status": "candidate",
            },
        )

        # 提交但不改变当前内容或问题状态
        await self.db.commit()
        await self.db.refresh(revision)

        return revision

    async def ignore_issue(self, issue_id: int, reason: str) -> ReviewIssue:
        """将问题标记为 ignored。"""
        await self._ensure_owned_novel()
        issue = await self.issue_repo.get(issue_id, self.novel_id)
        if not issue:
            raise NotFound("审阅问题不存在")
        if issue.status != "open":
            raise BadRequest("只能忽略 open 状态的问题")
        if not reason.strip():
            raise BadRequest("忽略原因不能为空")

        issue = await self.issue_repo.update(
            issue,
            {
                "status": "ignored",
                "ignored_reason": reason.strip(),
            },
        )
        await self.db.commit()
        await self.db.refresh(issue)
        return issue
