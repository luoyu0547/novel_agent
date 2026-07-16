"""phase 5 retrieval — RetrievalIndexJob table

Revision ID: b1c2d3e4f5a6
Revises: 0a1b2c3d4e5f
Create Date: 2026-07-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5a6"
down_revision = "0a1b2c3d4e5f"


def upgrade() -> None:
    op.create_table(
        "retrieval_index_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=True),
        sa.Column("tenant_key", sa.String(100), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retrieval_index_jobs_novel_id", "retrieval_index_jobs", ["novel_id"])
    op.create_index("ix_retrieval_index_jobs_tenant_key", "retrieval_index_jobs", ["tenant_key"])
    op.create_index(
        "ix_retrieval_jobs_claimable",
        "retrieval_index_jobs",
        ["status", "next_attempt_at", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_retrieval_jobs_claimable", table_name="retrieval_index_jobs")
    op.drop_index("ix_retrieval_index_jobs_tenant_key", table_name="retrieval_index_jobs")
    op.drop_index("ix_retrieval_index_jobs_novel_id", table_name="retrieval_index_jobs")
    op.drop_table("retrieval_index_jobs")
