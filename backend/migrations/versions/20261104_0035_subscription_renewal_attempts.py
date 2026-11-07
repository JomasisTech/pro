"""Add idempotent subscription renewal attempt ledger."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0035"
down_revision = "20261104_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_renewal_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_transaction_id", sa.Uuid(), sa.ForeignKey("payment_transactions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="processing", nullable=False),
        sa.Column("provider_status", sa.String(length=32), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_id", "period_end", name="uq_renewal_subscription_period"),
        sa.UniqueConstraint("payment_transaction_id"),
    )
    op.create_index("ix_renewal_attempt_status_created", "subscription_renewal_attempts", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_renewal_attempt_status_created", table_name="subscription_renewal_attempts")
    op.drop_table("subscription_renewal_attempts")
