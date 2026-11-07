"""Persist the selected billing interval on each payment attempt."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0031"
down_revision = "20261104_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_transactions", sa.Column("billing_interval", sa.String(16), nullable=False, server_default="monthly"))


def downgrade() -> None:
    op.drop_column("payment_transactions", "billing_interval")
