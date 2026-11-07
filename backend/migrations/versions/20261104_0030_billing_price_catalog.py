"""Add owner-managed NGN/USD price catalog and price-change audit trail."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0030"
down_revision = "20261104_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_prices",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("plan_id", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("billing_interval", sa.String(16), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("plan_id", "currency", "billing_interval", name="uq_billing_price_plan_currency_interval"),
    )
    op.create_table(
        "billing_price_changes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("price_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("plan_id", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("billing_interval", sa.String(16), nullable=False),
        sa.Column("previous_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("new_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("previous_enabled", sa.Boolean(), nullable=True),
        sa.Column("new_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_billing_price_changes_price_id", "billing_price_changes", ["price_id"])

    prices = sa.table(
        "billing_prices",
        sa.column("id", sa.Uuid(as_uuid=True)), sa.column("plan_id", sa.String),
        sa.column("currency", sa.String), sa.column("billing_interval", sa.String),
        sa.column("amount_minor", sa.BigInteger), sa.column("enabled", sa.Boolean),
    )
    import uuid
    seed = []
    amounts = {
        ("standard", "NGN", "monthly"): 750000,
        ("premium", "NGN", "monthly"): 1500000,
        ("standard", "USD", "monthly"): 999,
        ("premium", "USD", "monthly"): 1999,
        ("standard", "NGN", "annual"): 7500000,
        ("premium", "NGN", "annual"): 15000000,
        ("standard", "USD", "annual"): 9990,
        ("premium", "USD", "annual"): 19990,
    }
    for (plan, currency, interval), amount in amounts.items():
        seed.append({"id": uuid.uuid4(), "plan_id": plan, "currency": currency,
                     "billing_interval": interval, "amount_minor": amount, "enabled": True})
    op.bulk_insert(prices, seed)


def downgrade() -> None:
    op.drop_index("ix_billing_price_changes_price_id", table_name="billing_price_changes")
    op.drop_table("billing_price_changes")
    op.drop_table("billing_prices")
