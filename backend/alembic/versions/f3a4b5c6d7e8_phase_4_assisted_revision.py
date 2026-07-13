"""phase 4 assisted revision — DraftVersion, extended DraftRevision/ReviewIssue/PendingRepair

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-07-13 00:00:00.000000
"""

import hashlib

from alembic import op
import sqlalchemy as sa


revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"


def upgrade() -> None:
    # ── 1. Create draft_versions table ──────────────────────────────────
    op.create_table(
        "draft_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("chapter_id", sa.Integer(), nullable=True),
        sa.Column("writing_run_id", sa.Integer(), nullable=False),
        sa.Column("based_on_version_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("revision_sequence", sa.Integer(), nullable=False),
        sa.Column("acceptance_override_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"]),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
        sa.ForeignKeyConstraint(["writing_run_id"], ["writing_runs.id"]),
        sa.ForeignKeyConstraint(
            ["based_on_version_id"], ["draft_versions.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "writing_run_id", "version", name="uq_draft_versions_run_version"
        ),
    )
    op.create_index(
        op.f("ix_draft_versions_novel_id"),
        "draft_versions",
        ["novel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_draft_versions_writing_run_id"),
        "draft_versions",
        ["writing_run_id"],
        unique=False,
    )

    # ── 2. Extend draft_revisions ────────────────────────────────────────
    with op.batch_alter_table("draft_revisions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("draft_version_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "sequence",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "source_type",
                sa.String(),
                nullable=False,
                server_default=sa.text("'author_request'"),
            )
        )
        batch_op.add_column(
            sa.Column("source_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "base_revision_sequence",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "base_content_hash",
                sa.String(),
                nullable=False,
                server_default=sa.text("''"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "patches_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "expanded_scope",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "expanded_scope_reason", sa.Text(), nullable=True
            )
        )
        batch_op.create_foreign_key(
            "fk_draft_revisions_draft_version_id",
            "draft_versions",
            ["draft_version_id"],
            ["id"],
        )

    # ── 3. Extend review_issues ──────────────────────────────────────────
    with op.batch_alter_table("review_issues", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("chapter_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "resolution_mode",
                sa.String(),
                nullable=False,
                server_default=sa.text("'needs_intent'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "repair_options_json", sa.JSON(), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                "resolved_by_revision_id", sa.Integer(), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column("ignored_reason", sa.Text(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_review_issues_chapter_id",
            "chapters",
            ["chapter_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_review_issues_resolved_by_revision",
            "draft_revisions",
            ["resolved_by_revision_id"],
            ["id"],
        )

    # ── 4. Extend pending_repairs ────────────────────────────────────────
    with op.batch_alter_table("pending_repairs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("review_issue_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_pending_repairs_review_issue_id",
            "review_issues",
            ["review_issue_id"],
            ["id"],
        )

    # ── 5. Backfill v1 for existing WritingRuns ─────────────────────────
    conn = op.get_bind()

    # 5a. Insert one DraftVersion per WritingRun with non-empty draft_content
    rows = conn.execute(
        sa.text(
            "SELECT id, novel_id, draft_content, word_count, status "
            "FROM writing_runs "
            "WHERE draft_content IS NOT NULL AND draft_content != ''"
        )
    ).fetchall()

    for row in rows:
        if row.status in ("completed", "accepted"):
            dv_status = "accepted"
        elif row.status == "discarded":
            dv_status = "rejected"
        else:
            dv_status = "draft"

        max_ver = conn.execute(
            sa.text(
                "SELECT COALESCE(MAX(version), 0) FROM draft_versions "
                "WHERE writing_run_id = :rid"
            ),
            {"rid": row.id},
        ).scalar()

        conn.execute(
            sa.text(
                "INSERT INTO draft_versions "
                "(novel_id, writing_run_id, version, title, content, "
                "word_count, change_reason, status, revision_sequence, "
                "created_at, updated_at) "
                "VALUES (:novel_id, :writing_run_id, :version, :title, "
                ":content, :word_count, :change_reason, :status, "
                "0, datetime('now'), datetime('now'))"
            ),
            {
                "novel_id": row.novel_id,
                "writing_run_id": row.id,
                "version": max_ver + 1,
                "title": "v1",
                "content": row.draft_content,
                "word_count": row.word_count,
                "change_reason": "v1 backfill",
                "status": dv_status,
            },
        )

    # 5b. Backfill DraftRevision new fields
    revisions = conn.execute(
        sa.text(
            "SELECT id, writing_run_id, decision_id, base_content, status "
            "FROM draft_revisions ORDER BY id"
        )
    ).fetchall()

    for rev in revisions:
        # draft_version_id — find v1 for this run
        v1 = conn.execute(
            sa.text(
                "SELECT id FROM draft_versions "
                "WHERE writing_run_id = :rid ORDER BY version LIMIT 1"
            ),
            {"rid": rev.writing_run_id},
        ).fetchone()
        draft_version_id = v1[0] if v1 else None

        # sequence — monotonically increasing for applied rows, else 0
        if rev.status == "applied":
            seq = conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM draft_revisions "
                    "WHERE writing_run_id = :rid "
                    "AND id <= :id AND status = 'applied'"
                ),
                {"rid": rev.writing_run_id, "id": rev.id},
            ).scalar()
        else:
            seq = 0

        source_type = (
            "planning_decision" if rev.decision_id else "author_request"
        )
        content_hash = hashlib.sha256(
            (rev.base_content or "").encode("utf-8")
        ).hexdigest()

        conn.execute(
            sa.text(
                "UPDATE draft_revisions SET "
                "draft_version_id = :draft_version_id, "
                "sequence = :sequence, "
                "source_type = :source_type, "
                "source_id = :source_id, "
                "base_revision_sequence = :base_revision_sequence, "
                "base_content_hash = :base_content_hash, "
                "patches_json = :patches_json, "
                "expanded_scope = :expanded_scope "
                "WHERE id = :id"
            ),
            {
                "draft_version_id": draft_version_id,
                "sequence": seq,
                "source_type": source_type,
                "source_id": rev.decision_id,
                "base_revision_sequence": 0,
                "base_content_hash": content_hash,
                "patches_json": "[]",
                "expanded_scope": False,
                "id": rev.id,
            },
        )

    # ── 6. Normalize ReviewIssue data ────────────────────────────────────
    issues = conn.execute(
        sa.text("SELECT id, severity, acceptance_blocking FROM review_issues")
    ).fetchall()

    for issue in issues:
        # resolution_mode from old severity
        if issue.severity == "needs_intent":
            resolution_mode = "needs_intent"
        elif issue.severity == "auto_fixable":
            resolution_mode = "auto_fixable"
        else:
            resolution_mode = "needs_intent"

        # new severity from acceptance_blocking
        if issue.acceptance_blocking:
            new_severity = "blocking"
        elif issue.severity == "warning":
            new_severity = "minor"
        else:
            new_severity = "major"

        conn.execute(
            sa.text(
                "UPDATE review_issues SET "
                "resolution_mode = :resolution_mode, "
                "severity = :new_severity "
                "WHERE id = :id"
            ),
            {
                "resolution_mode": resolution_mode,
                "new_severity": new_severity,
                "id": issue.id,
            },
        )

    # ── 7. Remove temporary server defaults (keep nullable draft_version_id) ──
    with op.batch_alter_table("draft_revisions", schema=None) as batch_op:
        batch_op.alter_column("sequence", server_default=None)
        batch_op.alter_column("source_type", server_default=None)
        batch_op.alter_column("base_revision_sequence", server_default=None)
        batch_op.alter_column("base_content_hash", server_default=None)
        batch_op.alter_column("patches_json", server_default=None)
        batch_op.alter_column("expanded_scope", server_default=None)

    with op.batch_alter_table("review_issues", schema=None) as batch_op:
        batch_op.alter_column("resolution_mode", server_default=None)


def downgrade() -> None:
    # ── 1. Drop pending_repairs FK & column ──────────────────────────────
    with op.batch_alter_table("pending_repairs", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_pending_repairs_review_issue_id", type_="foreignkey"
        )
        batch_op.drop_column("review_issue_id")

    # ── 2. Drop review_issues FK & columns ───────────────────────────────
    with op.batch_alter_table("review_issues", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_review_issues_resolved_by_revision", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_review_issues_chapter_id", type_="foreignkey"
        )
        batch_op.drop_column("ignored_reason")
        batch_op.drop_column("resolved_by_revision_id")
        batch_op.drop_column("repair_options_json")
        batch_op.drop_column("resolution_mode")
        batch_op.drop_column("chapter_id")

    # ── 3. Drop draft_revisions FK & columns ─────────────────────────────
    with op.batch_alter_table("draft_revisions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_draft_revisions_draft_version_id", type_="foreignkey"
        )
        batch_op.drop_column("expanded_scope_reason")
        batch_op.drop_column("expanded_scope")
        batch_op.drop_column("patches_json")
        batch_op.drop_column("base_content_hash")
        batch_op.drop_column("base_revision_sequence")
        batch_op.drop_column("source_id")
        batch_op.drop_column("source_type")
        batch_op.drop_column("sequence")
        batch_op.drop_column("draft_version_id")

    # ── 4. Drop draft_versions table ─────────────────────────────────────
    op.drop_index(
        op.f("ix_draft_versions_writing_run_id"), table_name="draft_versions"
    )
    op.drop_index(
        op.f("ix_draft_versions_novel_id"), table_name="draft_versions"
    )
    op.drop_table("draft_versions")
