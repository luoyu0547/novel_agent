"""v2 phase 2 and phase 3 shared contracts

Revision ID: a1b2c3d4e5f6
Revises: 99a880fa2d58
Create Date: 2026-07-10 12:00:00.000000

"""
from typing import Collection, Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '99a880fa2d58'
branch_labels: str | Collection[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- volume_arcs ---
    op.create_table('volume_arcs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('novel_id', sa.Integer(), nullable=False),
        sa.Column('blueprint_id', sa.Integer(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('goal', sa.Text(), nullable=False),
        sa.Column('start_state', sa.Text(), nullable=False),
        sa.Column('end_state', sa.Text(), nullable=False),
        sa.Column('key_events', sa.JSON(), nullable=False),
        sa.Column('pacing_notes', sa.Text(), nullable=False),
        sa.Column('foreshadowing_plan', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['blueprint_id'], ['novel_blueprints.id'], ),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_volume_arcs_novel_id'), 'volume_arcs', ['novel_id'], unique=False)

    # --- plan_versions ---
    op.create_table('plan_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('novel_id', sa.Integer(), nullable=False),
        sa.Column('plan_type', sa.String(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('change_reason', sa.Text(), nullable=False),
        sa.Column('impact_scope', sa.Text(), nullable=False),
        sa.Column('snapshot_json', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plan_versions_novel_id'), 'plan_versions', ['novel_id'], unique=False)

    # --- review_issues ---
    op.create_table('review_issues',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('novel_id', sa.Integer(), nullable=False),
        sa.Column('writing_run_id', sa.Integer(), nullable=True),
        sa.Column('issue_type', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('location', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('related_memory', sa.Text(), nullable=True),
        sa.Column('suggestion', sa.Text(), nullable=False),
        sa.Column('acceptance_blocking', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], ),
        sa.ForeignKeyConstraint(['writing_run_id'], ['writing_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_issues_novel_id'), 'review_issues', ['novel_id'], unique=False)
    op.create_index(op.f('ix_review_issues_writing_run_id'), 'review_issues', ['writing_run_id'], unique=False)

    # --- writing_runs extensions ---
    op.add_column('writing_runs', sa.Column('mode', sa.String(), nullable=False, server_default='standard'))
    op.add_column('writing_runs', sa.Column('target_word_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('writing_runs', sa.Column('min_word_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('writing_runs', sa.Column('max_word_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('writing_runs', sa.Column('input_snapshot', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('writing_runs', sa.Column('agent_notes', sa.Text(), nullable=False, server_default=''))
    op.add_column('writing_runs', sa.Column('self_check', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('writing_runs', sa.Column('plan_version_ids', sa.JSON(), nullable=False, server_default='[]'))

    # --- pending_repairs.chapter_id -> nullable ---
    with op.batch_alter_table('pending_repairs', schema=None) as batch_op:
        batch_op.alter_column('chapter_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # pending_repairs.chapter_id -> not null
    with op.batch_alter_table('pending_repairs', schema=None) as batch_op:
        batch_op.alter_column('chapter_id', existing_type=sa.Integer(), nullable=False)

    op.drop_column('writing_runs', 'plan_version_ids')
    op.drop_column('writing_runs', 'self_check')
    op.drop_column('writing_runs', 'agent_notes')
    op.drop_column('writing_runs', 'input_snapshot')
    op.drop_column('writing_runs', 'max_word_count')
    op.drop_column('writing_runs', 'min_word_count')
    op.drop_column('writing_runs', 'target_word_count')
    op.drop_column('writing_runs', 'mode')

    op.drop_index(op.f('ix_review_issues_writing_run_id'), table_name='review_issues')
    op.drop_index(op.f('ix_review_issues_novel_id'), table_name='review_issues')
    op.drop_table('review_issues')

    op.drop_index(op.f('ix_plan_versions_novel_id'), table_name='plan_versions')
    op.drop_table('plan_versions')

    op.drop_index(op.f('ix_volume_arcs_novel_id'), table_name='volume_arcs')
    op.drop_table('volume_arcs')
