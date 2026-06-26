"""phase 1 novel chapter fields

Revision ID: 8f16e9c1a2b3
Revises: 23232ab11c17
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Collection, Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8f16e9c1a2b3"
down_revision: Optional[str] = "23232ab11c17"
branch_labels: Optional[Union[str, Collection[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.add_column("novels", sa.Column("genre", sa.String(length=100), nullable=True))
    op.add_column("novels", sa.Column("style_guide", sa.Text(), nullable=True))
    op.add_column("chapters", sa.Column("summary", sa.Text(), nullable=False, server_default=""))
    op.add_column("chapters", sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"))


def downgrade() -> None:
    op.drop_column("chapters", "status")
    op.drop_column("chapters", "summary")
    op.drop_column("novels", "style_guide")
    op.drop_column("novels", "genre")
