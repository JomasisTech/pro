"""Add one-time OAuth state and encrypted social credentials."""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0009"
down_revision = "20261102_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "social_oauth_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_social_oauth_states_state_hash", "social_oauth_states", ["state_hash"], unique=True)
    op.create_index("ix_social_oauth_states_organization_id", "social_oauth_states", ["organization_id"])
    op.create_index("ix_social_oauth_states_user_id", "social_oauth_states", ["user_id"])
    op.create_table(
        "social_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("access_token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("token_type", sa.String(length=32), server_default="bearer", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("social_account_id", name="uq_social_credential_account"),
    )
    op.create_index("ix_social_credentials_social_account_id", "social_credentials", ["social_account_id"])


def downgrade() -> None:
    op.drop_index("ix_social_credentials_social_account_id", table_name="social_credentials")
    op.drop_table("social_credentials")
    op.drop_index("ix_social_oauth_states_user_id", table_name="social_oauth_states")
    op.drop_index("ix_social_oauth_states_organization_id", table_name="social_oauth_states")
    op.drop_index("ix_social_oauth_states_state_hash", table_name="social_oauth_states")
    op.drop_table("social_oauth_states")
