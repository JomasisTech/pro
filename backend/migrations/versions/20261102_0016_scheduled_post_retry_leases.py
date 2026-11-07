"""Add retry scheduling and processing leases to scheduled posts."""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0016"
down_revision = "20261102_0015"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("scheduled_posts", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scheduled_posts", sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_scheduled_posts_retry", "scheduled_posts", ["status", "next_attempt_at"])

def downgrade() -> None:
    op.drop_index("ix_scheduled_posts_retry", table_name="scheduled_posts")
    op.drop_column("scheduled_posts", "processing_started_at")
    op.drop_column("scheduled_posts", "next_attempt_at")
