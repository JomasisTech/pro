"""Add subscription cancellation and renewal grace-period timestamps."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0033"
down_revision = "20261104_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("subscriptions", "cancellation_requested_at")
    op.drop_column("subscriptions", "grace_period_ends_at")
