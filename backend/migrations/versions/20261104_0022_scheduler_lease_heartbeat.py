"""Add renewable, owner-token scheduler leases."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0022"
down_revision = "20261104_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scheduled_posts", sa.Column("lease_token", sa.Uuid(), nullable=True))
    op.add_column("scheduled_posts", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_scheduled_posts_lease_token", "scheduled_posts", ["lease_token"])
    op.create_index("ix_scheduled_posts_lease_expires_at", "scheduled_posts", ["lease_expires_at"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_posts_lease_expires_at", table_name="scheduled_posts")
    op.drop_index("ix_scheduled_posts_lease_token", table_name="scheduled_posts")
    op.drop_column("scheduled_posts", "lease_expires_at")
    op.drop_column("scheduled_posts", "lease_token")
