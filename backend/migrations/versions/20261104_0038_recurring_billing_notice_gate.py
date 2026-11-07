"""Require delivery of a one-time notice before automatic renewal charges."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0038"
down_revision = "20261104_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("recurring_billing_notice_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("subscriptions", "recurring_billing_notice_sent_at")
