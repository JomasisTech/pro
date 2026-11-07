"""Persist external identity-provider subjects for social sign-in."""
from alembic import op
import sqlalchemy as sa
revision = "20261104_0023"
down_revision = "20261104_0022"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "auth_identities",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_subject", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_auth_identity_provider_subject"),
    )
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])

def downgrade() -> None:
    op.drop_index("ix_auth_identities_user_id", table_name="auth_identities")
    op.drop_table("auth_identities")
