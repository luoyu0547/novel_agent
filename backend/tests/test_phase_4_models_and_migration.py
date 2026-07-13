"""Phase 4 辅助修订——模型持久化边界测试与迁移往返测试。"""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.models.draft_version import DraftVersion
from app.models.plot_planning import DraftRevision
from app.models.quality_gate import ReviewIssue
from app.models.writing import PendingRepair, WritingRun
from app.models.novel import Novel
from app.models.user import User
from app.models.writing import ChapterBrief, ContextPackage, ChapterPlan


BACKEND_DIR = Path(__file__).resolve().parents[1]


def hash_content(s: str) -> str:
    """Consistent SHA-256 hash for content strings."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


async def make_user(db):
    """Create a minimal user for FK chains."""
    user = User(username="test_user", hashed_password="x")
    db.add(user)
    await db.flush()
    return user


async def make_writing_run(db, draft_content="", status="completed"):
    """Minimal helper to create a WritingRun with required FK chain."""
    user = await make_user(db)
    novel = Novel(
        title="测试",
        description="",
        genre="古风",
        style_guide="第三人称",
        user_id=user.id,
    )
    db.add(novel)
    await db.flush()

    cp_plan = ChapterPlan(novel_id=novel.id, position=1)
    db.add(cp_plan)
    await db.flush()

    cb = ChapterBrief(novel_id=novel.id, chapter_plan_id=cp_plan.id)
    db.add(cb)
    await db.flush()

    ctx = ContextPackage(novel_id=novel.id, chapter_brief_id=cb.id)
    db.add(ctx)
    await db.flush()

    run = WritingRun(
        novel_id=novel.id,
        chapter_brief_id=cb.id,
        context_package_id=ctx.id,
        draft_content=draft_content,
        status=status,
    )
    db.add(run)
    await db.flush()
    return run


# ── ORM 边界测试 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_draft_version_and_revision_are_separate_layers(db):
    """DraftVersion 与 DraftRevision 作为独立层次，通过 FK 关联。"""
    run = await make_writing_run(db, draft_content="初稿正文", status="completed")
    version = DraftVersion(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        version=1,
        title="首次生成",
        content="初稿正文",
        word_count=4,
        change_reason="首次生成",
        status="draft",
        revision_sequence=0,
    )
    db.add(version)
    await db.flush()

    revision = DraftRevision(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        draft_version_id=version.id,
        sequence=1,
        source_type="manual_edit",
        source_id=None,
        base_revision_sequence=0,
        base_content_hash=hash_content("初稿正文"),
        base_content="初稿正文",
        candidate_content="补充后的正文",
        patches_json=[],
        diff_json={"old": "初稿正文", "new": "补充后的正文"},
        scope_json={"type": "manual"},
        reason="补充角色动机",
        expanded_scope=False,
        status="applied",
    )
    db.add(revision)
    await db.flush()

    assert version.version == 1
    assert revision.draft_version_id == version.id
    assert revision.source_type == "manual_edit"
    assert revision.sequence == 1


@pytest.mark.asyncio
async def test_draft_version_acceptance_override_reason(db):
    """DraftVersion.acceptance_override_reason 可持久化。"""
    run = await make_writing_run(db, draft_content="正文", status="completed")
    version = DraftVersion(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        version=1,
        title="v1",
        content="正文",
        word_count=2,
        change_reason="首次生成",
        status="accepted",
        revision_sequence=0,
        acceptance_override_reason="作者手动确认",
    )
    db.add(version)
    await db.flush()

    loaded = await db.get(DraftVersion, version.id)
    assert loaded is not None
    assert loaded.acceptance_override_reason == "作者手动确认"
    assert loaded.status == "accepted"


@pytest.mark.asyncio
async def test_review_issue_extended_fields(db):
    """ReviewIssue 新增字段 (resolution_mode, repair_options_json, resolved_by_revision_id, ignored_reason) 可持久化。"""
    run = await make_writing_run(db, draft_content="测试", status="completed")

    issue = ReviewIssue(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        issue_type="continuity",
        severity="blocking",
        resolution_mode="auto_fixable",
        repair_options_json=[{"fix": "rewrite"}],
        ignored_reason=None,
        location="第3段",
        description="时间线矛盾",
        suggestion="统一日期",
        acceptance_blocking=True,
        status="open",
    )
    db.add(issue)
    await db.flush()

    loaded = await db.get(ReviewIssue, issue.id)
    assert loaded is not None
    assert loaded.resolution_mode == "auto_fixable"
    assert loaded.repair_options_json == [{"fix": "rewrite"}]


@pytest.mark.asyncio
async def test_review_issue_resolved_by_revision(db):
    """resolved_by_revision_id 可指向 DraftRevision。"""
    run = await make_writing_run(db, draft_content="内容", status="completed")
    version = DraftVersion(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        version=1,
        title="v1",
        content="内容",
        word_count=2,
        change_reason="首次生成",
        status="draft",
        revision_sequence=0,
    )
    db.add(version)
    await db.flush()

    revision = DraftRevision(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        draft_version_id=version.id,
        sequence=1,
        source_type="manual_edit",
        base_revision_sequence=0,
        base_content_hash=hash_content("内容"),
        base_content="内容",
        candidate_content="修改后内容",
        patches_json=[],
        diff_json={},
        scope_json={},
        reason="修正",
        expanded_scope=False,
        status="applied",
    )
    db.add(revision)
    await db.flush()

    issue = ReviewIssue(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        issue_type="continuity",
        severity="blocking",
        resolution_mode="needs_intent",
        resolved_by_revision_id=revision.id,
        location="x",
        description="y",
        suggestion="z",
        acceptance_blocking=True,
        status="resolved",
    )
    db.add(issue)
    await db.flush()

    loaded = await db.get(ReviewIssue, issue.id)
    assert loaded.resolved_by_revision_id == revision.id


@pytest.mark.asyncio
async def test_review_issue_ignored_reason(db):
    """ReviewIssue.ignored_reason 可持久化。"""
    run = await make_writing_run(db, status="completed")
    issue = ReviewIssue(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        issue_type="style",
        severity="minor",
        resolution_mode="needs_intent",
        ignored_reason="风格偏好不修改",
        location="x",
        description="y",
        suggestion="z",
        acceptance_blocking=False,
        status="ignored",
    )
    db.add(issue)
    await db.flush()

    loaded = await db.get(ReviewIssue, issue.id)
    assert loaded.ignored_reason == "风格偏好不修改"


@pytest.mark.asyncio
async def test_pending_repair_review_issue_id(db):
    """PendingRepair.review_issue_id 可指向 ReviewIssue。"""
    run = await make_writing_run(db, status="completed")
    issue = ReviewIssue(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        issue_type="task_completion",
        severity="blocking",
        resolution_mode="needs_intent",
        location="x",
        description="y",
        suggestion="z",
        acceptance_blocking=True,
        status="open",
    )
    db.add(issue)
    await db.flush()

    repair = PendingRepair(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        review_issue_id=issue.id,
        issue_type="task_completion",
        description="y",
        location="x",
        context="",
        options=[{"fix": "a"}],
        intent_type="author_request",
        status="pending",
    )
    db.add(repair)
    await db.flush()

    loaded = await db.get(PendingRepair, repair.id)
    assert loaded.review_issue_id == issue.id


@pytest.mark.asyncio
async def test_draft_revision_expanded_scope(db):
    """DraftRevision.expanded_scope 与 expanded_scope_reason 可持久化。"""
    run = await make_writing_run(db, draft_content="基础", status="completed")
    version = DraftVersion(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        version=1,
        title="v1",
        content="基础",
        word_count=2,
        change_reason="首次",
        status="draft",
        revision_sequence=0,
    )
    db.add(version)
    await db.flush()

    revision = DraftRevision(
        novel_id=run.novel_id,
        writing_run_id=run.id,
        draft_version_id=version.id,
        sequence=1,
        source_type="review_issue",
        base_revision_sequence=0,
        base_content_hash=hash_content("基础"),
        base_content="基础",
        candidate_content="扩展后的内容",
        patches_json=[],
        diff_json={},
        scope_json={},
        reason="修复问题",
        expanded_scope=True,
        expanded_scope_reason="需要额外补充一段背景说明",
        status="candidate",
    )
    db.add(revision)
    await db.flush()

    loaded = await db.get(DraftRevision, revision.id)
    assert loaded.expanded_scope is True
    assert loaded.expanded_scope_reason == "需要额外补充一段背景说明"


# ── 迁移往返测试 ────────────────────────────────────────────────


@pytest.mark.subprocess
def test_migration_round_trip(tmp_path):
    """使用 subprocess + tmp_path 执行真实迁移往返，验证回填逻辑。

    步骤:
        1. 升级到 e2f3a4b5c6d7 (Phase 3 最后一个迁移)
        2. 用 sqlite3 插入旧格式数据 (WritingRun, DraftRevision, ReviewIssue)
        3. 升级到 head → 验证 v1 回填、Revision 字段、ReviewIssue 归一化
        4. 降级到 e2f3a4b5c6d7 → 再次升级到 head → 验证幂等
    """
    db_path = tmp_path / "test_migration.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["APP_ENV"] = "test"
    # Remove any conftest-set DATABASE_URL that might conflict
    env.pop("_TEST_DB_SET", None)

    def run_alembic(*args, **kwargs):
        cmd = [sys.executable, "-m", "alembic"] + list(args)
        result = subprocess.run(
            cmd,
            cwd=str(BACKEND_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        return result

    # ── Step 1: 升级到 Phase 3 ──
    result = run_alembic("upgrade", "e2f3a4b5c6d7")
    assert result.returncode == 0, f"upgrade to e2f3a4b5c6d7 failed: {result.stderr}"

    # ── Step 2: 插入旧格式数据 ──
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript("PRAGMA foreign_keys = OFF;")

    NOW = "2026-01-01 12:00:00"

    # 2a. 插入 User + Novel
    conn.execute(
        "INSERT INTO users (id, username, hashed_password, created_at, updated_at) "
        "VALUES (1, 'mig_user', 'x', :now, :now)",
        {"now": NOW},
    )
    conn.execute(
        "INSERT INTO novels (id, user_id, title, description, genre, style_guide, "
        "created_at, updated_at) "
        "VALUES (1, 1, '迁移小说', '', '古风', 'SG', :now, :now)",
        {"now": NOW},
    )

    # 2b. 插入 WritingRun 依赖的元数据
    conn.execute(
        "INSERT INTO chapter_plans (id, novel_id, position, status, content_json, "
        "created_at, updated_at) "
        "VALUES (1, 1, 1, 'draft', '{}', :now, :now)",
        {"now": NOW},
    )
    conn.execute(
        "INSERT INTO chapter_briefs (id, novel_id, chapter_plan_id, status, brief_json, "
        "length_contract_json, created_at, updated_at) "
        "VALUES (1, 1, 1, 'draft', '{}', '{}', :now, :now)",
        {"now": NOW},
    )
    conn.execute(
        "INSERT INTO context_packages (id, novel_id, chapter_brief_id, package_json, "
        "created_at) "
        "VALUES (1, 1, 1, '{}', :now)",
        {"now": NOW},
    )

    # 2c. 插入 WritingRun (有 draft_content → 应回填 v1)
    conn.execute(
        "INSERT INTO writing_runs (id, novel_id, chapter_brief_id, context_package_id, "
        "status, draft_content, word_count, gate_result_json, gated, "
        "has_pending_repairs, context_snapshot_json, planning_blocked, "
        "created_at, updated_at) "
        "VALUES (101, 1, 1, 1, 'completed', '旧版正文内容', 6, '{}', 0, 0, '{}', 0, :now, :now)",
        {"now": NOW},
    )
    # 一个没有 draft_content 的 run → 不应产生 v1
    conn.execute(
        "INSERT INTO writing_runs (id, novel_id, chapter_brief_id, context_package_id, "
        "status, draft_content, word_count, gate_result_json, gated, "
        "has_pending_repairs, context_snapshot_json, planning_blocked, "
        "created_at, updated_at) "
        "VALUES (102, 1, 1, 1, 'running', '', 0, '{}', 0, 0, '{}', 0, :now, :now)",
        {"now": NOW},
    )

    # 2d. 插入旧格式 DraftRevision（无新字段）
    conn.execute(
        "INSERT INTO draft_revisions (id, novel_id, writing_run_id, parent_revision_id, "
        "decision_id, base_content, candidate_content, scope_json, diff_json, "
        "reason, status, created_at, updated_at) "
        "VALUES (201, 1, 101, NULL, NULL, 'base', 'candidate', '{}', '{}', '首次', 'applied', :now, :now)",
        {"now": NOW},
    )
    conn.execute(
        "INSERT INTO draft_revisions (id, novel_id, writing_run_id, parent_revision_id, "
        "decision_id, base_content, candidate_content, scope_json, diff_json, "
        "reason, status, created_at, updated_at) "
        "VALUES (202, 1, 101, 201, 1, 'base2', 'candidate2', '{}', '{}', '二次', 'candidate', :now, :now)",
        {"now": NOW},
    )
    conn.execute(
        "INSERT INTO draft_revisions (id, novel_id, writing_run_id, parent_revision_id, "
        "decision_id, base_content, candidate_content, scope_json, diff_json, "
        "reason, status, created_at, updated_at) "
        "VALUES (203, 1, 101, 201, NULL, 'base3', 'candidate3', '{}', '{}', '三次', 'applied', :now, :now)",
        {"now": NOW},
    )

    # 2e. 插入旧格式 ReviewIssue（无新字段）
    conn.execute(
        "INSERT INTO review_issues (id, novel_id, writing_run_id, issue_type, severity, "
        "location, description, related_memory, suggestion, acceptance_blocking, status, "
        "created_at, updated_at) "
        "VALUES (301, 1, 101, 'continuity', 'needs_intent', 'loc', 'desc', NULL, 'sug', 1, 'open', :now, :now)",
        {"now": NOW},
    )
    conn.execute(
        "INSERT INTO review_issues (id, novel_id, writing_run_id, issue_type, severity, "
        "location, description, related_memory, suggestion, acceptance_blocking, status, "
        "created_at, updated_at) "
        "VALUES (302, 1, 101, 'style', 'auto_fixable', 'loc2', 'desc2', NULL, 'sug2', 0, 'open', :now, :now)",
        {"now": NOW},
    )
    conn.execute(
        "INSERT INTO review_issues (id, novel_id, writing_run_id, issue_type, severity, "
        "location, description, related_memory, suggestion, acceptance_blocking, status, "
        "created_at, updated_at) "
        "VALUES (303, 1, 101, 'style', 'warning', 'loc3', 'desc3', NULL, 'sug3', 0, 'open', :now, :now)",
        {"now": NOW},
    )

    # 2f. 插入一个 planning_decision 供 draft_revision 202 引用
    conn.execute(
        "INSERT INTO planning_decisions (id, novel_id, source, status, conflict_summary, "
        "evidence_json, options_json, recommended_index, recommendation_reason, "
        "impact_scope_json, created_at, updated_at) "
        "VALUES (1, 1, 'quality_gate', 'resolved', '', '{}', '[]', 0, '', '{}', :now, :now)",
        {"now": NOW},
    )

    conn.commit()
    conn.close()

    # ── Step 3: 升级到 head ──
    result = run_alembic("upgrade", "head")
    assert result.returncode == 0, f"upgrade to head failed: {result.stderr}"

    # ── Step 4: 验证回填 (Verify backfill) ──
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 4a. WritingRun 101 (有 draft_content) 应产生了 v1
    rows = conn.execute(
        "SELECT * FROM draft_versions WHERE writing_run_id = 101"
    ).fetchall()
    assert len(rows) == 1, f"Expected 1 DraftVersion for run 101, got {len(rows)}"
    v1 = rows[0]
    assert v1["version"] == 1
    assert v1["title"] == "v1"
    assert v1["content"] == "旧版正文内容"
    assert v1["status"] == "accepted"  # completed → accepted
    assert v1["word_count"] == 6

    # WritingRun 102 (空 draft_content) 不应产生 v1
    rows2 = conn.execute(
        "SELECT * FROM draft_versions WHERE writing_run_id = 102"
    ).fetchall()
    assert len(rows2) == 0, f"Expected 0 DraftVersion for run 102, got {len(rows2)}"

    # 4b. DraftRevision 201 (status=applied) → sequence=1, source_type=author_request
    r201 = conn.execute(
        "SELECT * FROM draft_revisions WHERE id = 201"
    ).fetchone()
    assert r201 is not None
    assert r201["draft_version_id"] == v1["id"], "Legacy revision should get v1 id"
    assert r201["source_type"] == "author_request"
    assert r201["source_id"] is None
    assert r201["base_revision_sequence"] == 0
    assert r201["patches_json"] == "[]"

    # 4c. DraftRevision 202 (status=candidate) → sequence=0
    r202 = conn.execute(
        "SELECT * FROM draft_revisions WHERE id = 202"
    ).fetchone()
    assert r202["sequence"] == 0

    # 4d. DraftRevision 203 (status=applied, second one) → sequence=2
    r203 = conn.execute(
        "SELECT * FROM draft_revisions WHERE id = 203"
    ).fetchone()
    assert r203["sequence"] == 2  # monotonically increasing for applied rows

    # 4e. ReviewIssue 301: old severity='needs_intent' → resolution_mode='needs_intent'
    ri301 = conn.execute(
        "SELECT * FROM review_issues WHERE id = 301"
    ).fetchone()
    assert ri301["resolution_mode"] == "needs_intent"
    assert ri301["severity"] == "blocking"  # acceptance_blocking=1

    # 4f. ReviewIssue 302: old severity='auto_fixable' → resolution_mode='auto_fixable'
    ri302 = conn.execute(
        "SELECT * FROM review_issues WHERE id = 302"
    ).fetchone()
    assert ri302["resolution_mode"] == "auto_fixable"
    assert ri302["severity"] == "major"  # acceptance_blocking=0, default

    # 4g. ReviewIssue 303: old severity='warning' → severity='minor'
    ri303 = conn.execute(
        "SELECT * FROM review_issues WHERE id = 303"
    ).fetchone()
    assert ri303["severity"] == "minor"

    conn.close()

    # ── Step 5: 降级到 e2f3a4b5c6d7 ──
    result = run_alembic("downgrade", "e2f3a4b5c6d7")
    assert result.returncode == 0, f"downgrade failed: {result.stderr}"

    # 验证新表和列已移除
    conn = sqlite3.connect(str(db_path))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {t[0] for t in tables}
    assert "draft_versions" not in table_names, "draft_versions should be dropped"

    # 验证旧字段恢复: review_issues 不应有 resolution_mode
    cols = conn.execute("PRAGMA table_info(review_issues)").fetchall()
    col_names = {c[1] for c in cols}
    assert "resolution_mode" not in col_names
    assert "chapter_id" not in col_names
    conn.close()

    # ── Step 6: 再次升级到 head（幂等验证）──
    result = run_alembic("upgrade", "head")
    assert result.returncode == 0, f"re-upgrade to head failed: {result.stderr}"

    # 验证 v1 数据仍然存在
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT * FROM draft_versions WHERE writing_run_id = 101"
    ).fetchall()
    assert len(rows) == 1, f"After re-upgrade, expected 1 DV, got {len(rows)}"
    conn.close()
