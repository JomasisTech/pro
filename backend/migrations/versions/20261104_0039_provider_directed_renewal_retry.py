"""Persist Paystack-directed retry windows for recurring authorization charges."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0039"
down_revision = "20261104_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscription_renewal_attempts", sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscription_renewal_attempts", sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("subscription_renewal_attempts", sa.Column("previous_reference", sa.String(length=120), nullable=True))
    op.create_index("ix_renewal_attempt_retry_at", "subscription_renewal_attempts", ["status", "retry_at"])


def downgrade() -> None:
    op.drop_index("ix_renewal_attempt_retry_at", table_name="subscription_renewal_attempts")
    op.drop_column("subscription_renewal_attempts", "previous_reference")
    op.drop_column("subscription_renewal_attempts", "retry_count")
    op.drop_column("subscription_renewal_attempts", "retry_at")
