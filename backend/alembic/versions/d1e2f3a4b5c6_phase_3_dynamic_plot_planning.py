"""phase_3_dynamic_plot_planning

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b8
Create Date: 2026-07-10 21:01:14.863553

"""
from typing import Collection, Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: str | None = 'c3d4e5f6a7b8'
branch_labels: str | Collection[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('planning_decisions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('novel_id', sa.Integer(), nullable=False),
    sa.Column('plot_unit_id', sa.Integer(), nullable=True),
    sa.Column('plot_plan_revision_id', sa.Integer(), nullable=True),
    sa.Column('chapter_brief_id', sa.Integer(), nullable=True),
    sa.Column('writing_run_id', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('conflict_summary', sa.Text(), nullable=False),
    sa.Column('evidence_json', sa.JSON(), nullable=False),
    sa.Column('options_json', sa.JSON(), nullable=False),
    sa.Column('recommended_index', sa.Integer(), nullable=False),
    sa.Column('recommendation_reason', sa.Text(), nullable=False),
    sa.Column('impact_scope_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['chapter_brief_id'], ['chapter_briefs.id'], ),
    sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], ),
    sa.ForeignKeyConstraint(['plot_plan_revision_id'], ['plot_plan_revisions.id'], ),
    sa.ForeignKeyConstraint(['plot_unit_id'], ['plot_units.id'], ),
    sa.ForeignKeyConstraint(['writing_run_id'], ['writing_runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_planning_decisions_novel_id'), 'planning_decisions', ['novel_id'], unique=False)
    op.create_table('author_foundations',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('novel_id', sa.Integer(), nullable=False),
    sa.Column('outline', sa.Text(), nullable=False),
    sa.Column('current_intent', sa.Text(), nullable=False),
    sa.Column('stage_goal', sa.Text(), nullable=False),
    sa.Column('constraints_json', sa.JSON(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_author_foundations_novel_id'), 'author_foundations', ['novel_id'], unique=True)
    op.create_table('draft_revisions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('novel_id', sa.Integer(), nullable=False),
    sa.Column('writing_run_id', sa.Integer(), nullable=True),
    sa.Column('parent_revision_id', sa.Integer(), nullable=True),
    sa.Column('decision_id', sa.Integer(), nullable=True),
    sa.Column('base_content', sa.Text(), nullable=False),
    sa.Column('candidate_content', sa.Text(), nullable=False),
    sa.Column('scope_json', sa.JSON(), nullable=False),
    sa.Column('diff_json', sa.JSON(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['decision_id'], ['planning_decisions.id'], ),
    sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], ),
    sa.ForeignKeyConstraint(['parent_revision_id'], ['draft_revisions.id'], ),
    sa.ForeignKeyConstraint(['writing_run_id'], ['writing_runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_draft_revisions_novel_id'), 'draft_revisions', ['novel_id'], unique=False)
    op.create_table('author_foundation_revisions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('novel_id', sa.Integer(), nullable=False),
    sa.Column('foundation_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('snapshot_json', sa.JSON(), nullable=False),
    sa.Column('change_reason', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['foundation_id'], ['author_foundations.id'], ),
    sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_author_foundation_revisions_foundation_id'), 'author_foundation_revisions', ['foundation_id'], unique=False)
    op.create_index(op.f('ix_author_foundation_revisions_novel_id'), 'author_foundation_revisions', ['novel_id'], unique=False)
    op.create_table('plot_units',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('novel_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('scope_type', sa.String(), nullable=False),
    sa.Column('start_position', sa.Integer(), nullable=False),
    sa.Column('end_position', sa.Integer(), nullable=False),
    sa.Column('author_goal', sa.Text(), nullable=False),
    sa.Column('start_state', sa.Text(), nullable=False),
    sa.Column('end_state', sa.Text(), nullable=False),
    sa.Column('foundation_revision_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['foundation_revision_id'], ['author_foundation_revisions.id'], ),
    sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plot_units_novel_id'), 'plot_units', ['novel_id'], unique=False)
    op.create_table('plot_plan_revisions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('novel_id', sa.Integer(), nullable=False),
    sa.Column('plot_unit_id', sa.Integer(), nullable=False),
    sa.Column('foundation_revision_id', sa.Integer(), nullable=False),
    sa.Column('based_on_published_chapter_id', sa.Integer(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('plan_json', sa.JSON(), nullable=False),
    sa.Column('change_reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['based_on_published_chapter_id'], ['chapters.id'], ),
    sa.ForeignKeyConstraint(['foundation_revision_id'], ['author_foundation_revisions.id'], ),
    sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], ),
    sa.ForeignKeyConstraint(['plot_unit_id'], ['plot_units.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plot_plan_revisions_novel_id'), 'plot_plan_revisions', ['novel_id'], unique=False)
    op.create_index(op.f('ix_plot_plan_revisions_plot_unit_id'), 'plot_plan_revisions', ['plot_unit_id'], unique=False)
    with op.batch_alter_table("writing_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column('decision_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('context_snapshot_json', sa.JSON(), nullable=False))
        batch_op.add_column(sa.Column('planning_blocked', sa.Boolean(), nullable=False))
        batch_op.create_foreign_key("fk_writing_runs_decision_id", "planning_decisions", ["decision_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("writing_runs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_writing_runs_decision_id", type_="foreignkey")
        batch_op.drop_column("planning_blocked")
        batch_op.drop_column("context_snapshot_json")
        batch_op.drop_column("decision_id")
    op.drop_index(op.f('ix_plot_plan_revisions_plot_unit_id'), table_name='plot_plan_revisions')
    op.drop_index(op.f('ix_plot_plan_revisions_novel_id'), table_name='plot_plan_revisions')
    op.drop_table('plot_plan_revisions')
    op.drop_index(op.f('ix_plot_units_novel_id'), table_name='plot_units')
    op.drop_table('plot_units')
    op.drop_index(op.f('ix_author_foundation_revisions_novel_id'), table_name='author_foundation_revisions')
    op.drop_index(op.f('ix_author_foundation_revisions_foundation_id'), table_name='author_foundation_revisions')
    op.drop_table('author_foundation_revisions')
    op.drop_index(op.f('ix_draft_revisions_novel_id'), table_name='draft_revisions')
    op.drop_table('draft_revisions')
    op.drop_index(op.f('ix_author_foundations_novel_id'), table_name='author_foundations')
    op.drop_table('author_foundations')
    op.drop_index(op.f('ix_planning_decisions_novel_id'), table_name='planning_decisions')
    op.drop_table('planning_decisions')
