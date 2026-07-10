"""task6: extend chapter_plans with planning fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-10 14:00:00.000000

"""
from typing import Collection, Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Collection[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- chapter_plans extensions ---
    op.add_column('chapter_plans', sa.Column('blueprint_id', sa.Integer(), nullable=True))
    op.add_column('chapter_plans', sa.Column('volume_arc_id', sa.Integer(), nullable=True))
    op.add_column('chapter_plans', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('chapter_plans', sa.Column('emotional_effect', sa.Text(), nullable=False, server_default=''))
    op.add_column('chapter_plans', sa.Column('target_word_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('chapter_plans', sa.Column('foreshadowing_tasks', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('chapter_plans', sa.Column('acceptance_criteria', sa.Text(), nullable=False, server_default=''))

    with op.batch_alter_table('chapter_plans', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_chapter_plans_blueprint_id', 'novel_blueprints', ['blueprint_id'], ['id'])
        batch_op.create_foreign_key('fk_chapter_plans_volume_arc_id', 'volume_arcs', ['volume_arc_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('chapter_plans', schema=None) as batch_op:
        batch_op.drop_constraint('fk_chapter_plans_volume_arc_id', type_='foreignkey')
        batch_op.drop_constraint('fk_chapter_plans_blueprint_id', type_='foreignkey')

    op.drop_column('chapter_plans', 'acceptance_criteria')
    op.drop_column('chapter_plans', 'foreshadowing_tasks')
    op.drop_column('chapter_plans', 'target_word_count')
    op.drop_column('chapter_plans', 'emotional_effect')
    op.drop_column('chapter_plans', 'version')
    op.drop_column('chapter_plans', 'volume_arc_id')
    op.drop_column('chapter_plans', 'blueprint_id')
