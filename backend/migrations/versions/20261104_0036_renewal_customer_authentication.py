"""Persist Paystack customer-authentication handoff for renewal attempts."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0036"
down_revision = "20261104_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscription_renewal_attempts", sa.Column("authorization_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("subscription_renewal_attempts", "authorization_url")
