"""Track verified refunds and chargeback outcomes."""
from alembic import op
import sqlalchemy as sa
revision = "20261107_0046"
down_revision = "20261107_0045"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("payment_adjustments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False, server_default="paystack"),
        sa.Column("provider_event_key", sa.String(length=128), nullable=False),
        sa.Column("provider_adjustment_id", sa.String(length=100), nullable=True),
        sa.Column("adjustment_type", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["payment_transaction_id"], ["payment_transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("provider_event_key"))
    op.create_index("ix_payment_adjustments_type_status_created", "payment_adjustments", ["adjustment_type", "status", "created_at"])
    op.create_index("ix_payment_adjustments_payment", "payment_adjustments", ["payment_transaction_id"])

def downgrade() -> None:
    op.drop_index("ix_payment_adjustments_payment", table_name="payment_adjustments")
    op.drop_index("ix_payment_adjustments_type_status_created", table_name="payment_adjustments")
    op.drop_table("payment_adjustments")
