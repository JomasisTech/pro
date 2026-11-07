"""Add organization-scoped social account metadata."""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0008"
down_revision = "20261102_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "social_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_account_id", sa.String(length=200), nullable=False),
        sa.Column("account_name", sa.String(length=200), nullable=False),
        sa.Column("account_type", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="connected", nullable=False),
        sa.Column("granted_scopes", sa.JSON(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "provider", "provider_account_id", name="uq_social_account_provider_identity"),
    )
    op.create_index("ix_social_accounts_organization_id", "social_accounts", ["organization_id"])
    op.create_index("ix_social_accounts_provider", "social_accounts", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_social_accounts_provider", table_name="social_accounts")
    op.drop_index("ix_social_accounts_organization_id", table_name="social_accounts")
    op.drop_table("social_accounts")
