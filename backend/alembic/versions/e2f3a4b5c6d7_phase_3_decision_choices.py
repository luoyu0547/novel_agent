"""phase 3 decision choices

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-07-12 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"

def upgrade():
    op.add_column("planning_decisions", sa.Column("selected_option_index", sa.Integer(), nullable=True))
    op.add_column("planning_decisions", sa.Column("custom_intent", sa.Text(), nullable=True))

def downgrade():
    op.drop_column("planning_decisions", "custom_intent")
    op.drop_column("planning_decisions", "selected_option_index")
