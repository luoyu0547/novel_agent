"""repair retrieval job completion timestamp on existing databases"""

from alembic import op
import sqlalchemy as sa


revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("retrieval_index_jobs")}
    if "completed_at" not in columns:
        op.add_column(
            "retrieval_index_jobs",
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    # The base Phase 5 migration already declares this column. Keeping it on
    # downgrade preserves both fresh databases and repaired legacy databases.
    pass
