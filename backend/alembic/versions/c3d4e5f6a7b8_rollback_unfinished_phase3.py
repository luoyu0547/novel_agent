"""Rollback the unfinished Phase 3 planning schema.

The earlier shared-contract migrations remain in history for databases that
may already have applied them. This migration returns the runtime schema to
the Phase 2 boundary while keeping the Phase 2 review-issue table and the
nullable pending-repair chapter reference.
"""

from typing import Collection, Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Collection[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chapter_plans", schema=None) as batch_op:
        batch_op.drop_constraint("fk_chapter_plans_volume_arc_id", type_="foreignkey")
        batch_op.drop_constraint("fk_chapter_plans_blueprint_id", type_="foreignkey")

    for column in (
        "acceptance_criteria",
        "foreshadowing_tasks",
        "target_word_count",
        "emotional_effect",
        "version",
        "volume_arc_id",
        "blueprint_id",
    ):
        op.drop_column("chapter_plans", column)

    for column in (
        "plan_version_ids",
        "self_check",
        "agent_notes",
        "input_snapshot",
        "max_word_count",
        "min_word_count",
        "target_word_count",
        "mode",
    ):
        op.drop_column("writing_runs", column)

    op.drop_index(op.f("ix_plan_versions_novel_id"), table_name="plan_versions")
    op.drop_table("plan_versions")
    op.drop_index(op.f("ix_volume_arcs_novel_id"), table_name="volume_arcs")
    op.drop_table("volume_arcs")


def downgrade() -> None:
    op.create_table(
        "volume_arcs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("blueprint_id", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("start_state", sa.Text(), nullable=False),
        sa.Column("end_state", sa.Text(), nullable=False),
        sa.Column("key_events", sa.JSON(), nullable=False),
        sa.Column("pacing_notes", sa.Text(), nullable=False),
        sa.Column("foreshadowing_plan", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["blueprint_id"], ["novel_blueprints.id"]),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_volume_arcs_novel_id"), "volume_arcs", ["novel_id"], unique=False)

    op.create_table(
        "plan_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("plan_type", sa.String(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("impact_scope", sa.Text(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_plan_versions_novel_id"), "plan_versions", ["novel_id"], unique=False)

    op.add_column("writing_runs", sa.Column("mode", sa.String(), nullable=False, server_default="standard"))
    op.add_column("writing_runs", sa.Column("target_word_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("writing_runs", sa.Column("min_word_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("writing_runs", sa.Column("max_word_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("writing_runs", sa.Column("input_snapshot", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("writing_runs", sa.Column("agent_notes", sa.Text(), nullable=False, server_default=""))
    op.add_column("writing_runs", sa.Column("self_check", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("writing_runs", sa.Column("plan_version_ids", sa.JSON(), nullable=False, server_default="[]"))

    op.add_column("chapter_plans", sa.Column("blueprint_id", sa.Integer(), nullable=True))
    op.add_column("chapter_plans", sa.Column("volume_arc_id", sa.Integer(), nullable=True))
    op.add_column("chapter_plans", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("chapter_plans", sa.Column("emotional_effect", sa.Text(), nullable=False, server_default=""))
    op.add_column("chapter_plans", sa.Column("target_word_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("chapter_plans", sa.Column("foreshadowing_tasks", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("chapter_plans", sa.Column("acceptance_criteria", sa.Text(), nullable=False, server_default=""))
    with op.batch_alter_table("chapter_plans", schema=None) as batch_op:
        batch_op.create_foreign_key("fk_chapter_plans_blueprint_id", "novel_blueprints", ["blueprint_id"], ["id"])
        batch_op.create_foreign_key("fk_chapter_plans_volume_arc_id", "volume_arcs", ["volume_arc_id"], ["id"])
