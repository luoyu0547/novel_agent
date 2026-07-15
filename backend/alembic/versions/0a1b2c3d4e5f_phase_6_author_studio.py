"""phase 6 author studio — WritingSession, WritingMessage, DraftWorkingCopy, WritingRun.writing_session_id

Revision ID: 0a1b2c3d4e5f
Revises: f3a4b5c6d7e8
Create Date: 2026-07-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0a1b2c3d4e5f"
down_revision = "f3a4b5c6d7e8"


def upgrade() -> None:
    # ── 1. Create writing_sessions table ─────────────────────────────────
    op.create_table(
        "writing_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("target_chapter_id", sa.Integer(), nullable=True),
        sa.Column("active_writing_run_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"]),
        sa.ForeignKeyConstraint(["target_chapter_id"], ["chapters.id"]),
        sa.ForeignKeyConstraint(["active_writing_run_id"], ["writing_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_writing_sessions_novel_id"),
        "writing_sessions",
        ["novel_id"],
        unique=False,
    )

    # ── 2. Create writing_messages table ─────────────────────────────────
    op.create_table(
        "writing_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("action_status", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("writing_run_id", sa.Integer(), nullable=True),
        sa.Column("context_package_id", sa.Integer(), nullable=True),
        sa.Column("draft_version_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["writing_sessions.id"]),
        sa.ForeignKeyConstraint(["writing_run_id"], ["writing_runs.id"]),
        sa.ForeignKeyConstraint(["context_package_id"], ["context_packages.id"]),
        sa.ForeignKeyConstraint(["draft_version_id"], ["draft_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        op.f("ix_writing_messages_session_id"),
        "writing_messages",
        ["session_id"],
        unique=False,
    )

    # ── 3. Create draft_working_copies table ─────────────────────────────
    op.create_table(
        "draft_working_copies",
        sa.Column("writing_run_id", sa.Integer(), nullable=False),
        sa.Column("draft_version_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("base_revision_sequence", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["writing_run_id"], ["writing_runs.id"]),
        sa.ForeignKeyConstraint(["draft_version_id"], ["draft_versions.id"]),
        sa.PrimaryKeyConstraint("writing_run_id"),
    )

    # ── 4. Add writing_session_id to writing_runs ────────────────────────
    with op.batch_alter_table("writing_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("writing_session_id", sa.Integer(), nullable=True)
        )
        batch_op.create_index(
            "ix_writing_runs_writing_session_id",
            ["writing_session_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_writing_runs_writing_session_id",
            "writing_sessions",
            ["writing_session_id"],
            ["id"],
        )


def downgrade() -> None:
    # ── 1. Drop writing_session_id from writing_runs ─────────────────────
    with op.batch_alter_table("writing_runs", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_writing_runs_writing_session_id", type_="foreignkey"
        )
        batch_op.drop_index("ix_writing_runs_writing_session_id")
        batch_op.drop_column("writing_session_id")

    # ── 2. Drop draft_working_copies table ───────────────────────────────
    op.drop_table("draft_working_copies")

    # ── 3. Drop writing_messages table ───────────────────────────────────
    op.drop_index(
        op.f("ix_writing_messages_session_id"), table_name="writing_messages"
    )
    op.drop_table("writing_messages")

    # ── 4. Drop writing_sessions table ───────────────────────────────────
    op.drop_index(
        op.f("ix_writing_sessions_novel_id"), table_name="writing_sessions"
    )
    op.drop_table("writing_sessions")
