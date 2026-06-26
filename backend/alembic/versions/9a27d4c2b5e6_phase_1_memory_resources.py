"""phase 1 memory resources

Revision ID: 9a27d4c2b5e6
Revises: 8f16e9c1a2b3
Create Date: 2026-06-26 00:00:01.000000

"""
from typing import Collection, Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9a27d4c2b5e6"
down_revision: Optional[str] = "8f16e9c1a2b3"
branch_labels: Optional[Union[str, Collection[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "character_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("story_role", sa.String(length=200), nullable=False),
        sa.Column("identity", sa.String(length=200), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("motivation", sa.Text(), nullable=False),
        sa.Column("speech_style", sa.Text(), nullable=False),
        sa.Column("behavior_rules", sa.JSON(), nullable=False),
        sa.Column("current_state", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "world_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("world_settings")
    op.drop_table("character_profiles")
