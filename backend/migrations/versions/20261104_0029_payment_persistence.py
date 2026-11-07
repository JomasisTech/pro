"""Add durable payment, subscription and webhook idempotency records."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0029"
down_revision = "20261104_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("initiated_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(24), nullable=False, server_default="paystack"),
        sa.Column("reference", sa.String(120), nullable=False, unique=True),
        sa.Column("plan_id", sa.String(32), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("customer_email", sa.String(320), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("provider_transaction_id", sa.String(80), nullable=True, unique=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payment_transactions_org_created", "payment_transactions", ["organization_id", "created_at"])
    op.create_index("ix_payment_transactions_status_created", "payment_transactions", ["status", "created_at"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("provider", sa.String(24), nullable=False, server_default="paystack"),
        sa.Column("plan_id", sa.String(32), nullable=False, server_default="free"),
        sa.Column("status", sa.String(24), nullable=False, server_default="inactive"),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("billing_interval", sa.String(16), nullable=True),
        sa.Column("provider_customer_code", sa.String(100), nullable=True),
        sa.Column("provider_subscription_code", sa.String(120), nullable=True, unique=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(24), nullable=False, server_default="paystack"),
        sa.Column("event_key", sa.String(128), nullable=False, unique=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("transaction_reference", sa.String(120), nullable=True),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_message", sa.String(400), nullable=True),
    )
    op.create_index("ix_payment_webhook_events_status_received", "payment_webhook_events", ["status", "received_at"])
    op.create_index("ix_payment_webhook_events_transaction_reference", "payment_webhook_events", ["transaction_reference"])


def downgrade() -> None:
    op.drop_index("ix_payment_webhook_events_transaction_reference", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_status_received", table_name="payment_webhook_events")
    op.drop_table("payment_webhook_events")
    op.drop_table("subscriptions")
    op.drop_index("ix_payment_transactions_status_created", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_org_created", table_name="payment_transactions")
    op.drop_table("payment_transactions")
