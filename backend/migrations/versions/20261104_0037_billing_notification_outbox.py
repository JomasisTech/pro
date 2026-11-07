"""Add durable billing email notification outbox."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0037"
down_revision = "20261104_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), sa.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("renewal_attempt_id", sa.Uuid(), sa.ForeignKey("subscription_renewal_attempts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_key", sa.String(length=240), nullable=False),
        sa.Column("notification_type", sa.String(length=40), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_billing_notification_event_key"),
    )
    op.create_index("ix_billing_notification_delivery", "billing_notifications", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_billing_notification_delivery", table_name="billing_notifications")
    op.drop_table("billing_notifications")
