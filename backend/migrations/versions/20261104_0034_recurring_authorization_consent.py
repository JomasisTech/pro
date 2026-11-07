"""Store explicit recurring consent and encrypted reusable Paystack authorization."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0034"
down_revision = "20261104_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_transactions", sa.Column("recurring_consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payment_transactions", sa.Column("recurring_consent_version", sa.String(length=32), nullable=True))
    op.add_column("payment_transactions", sa.Column("recurring_consent_text", sa.Text(), nullable=True))
    op.add_column("subscriptions", sa.Column("provider_authorization_code_encrypted", sa.LargeBinary(), nullable=True))
    op.add_column("subscriptions", sa.Column("provider_authorization_email", sa.String(length=320), nullable=True))
    op.add_column("subscriptions", sa.Column("provider_authorization_reusable", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("subscriptions", sa.Column("authorization_card_last4", sa.String(length=4), nullable=True))
    op.add_column("subscriptions", sa.Column("authorization_card_type", sa.String(length=40), nullable=True))
    op.add_column("subscriptions", sa.Column("authorization_card_exp_month", sa.String(length=2), nullable=True))
    op.add_column("subscriptions", sa.Column("authorization_card_exp_year", sa.String(length=4), nullable=True))
    op.add_column("subscriptions", sa.Column("recurring_consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("recurring_consent_version", sa.String(length=32), nullable=True))


def downgrade() -> None:
    for column in ("recurring_consent_version", "recurring_consent_at", "authorization_card_exp_year", "authorization_card_exp_month", "authorization_card_type", "authorization_card_last4", "provider_authorization_reusable", "provider_authorization_email", "provider_authorization_code_encrypted"):
        op.drop_column("subscriptions", column)
    for column in ("recurring_consent_text", "recurring_consent_version", "recurring_consent_at"):
        op.drop_column("payment_transactions", column)
