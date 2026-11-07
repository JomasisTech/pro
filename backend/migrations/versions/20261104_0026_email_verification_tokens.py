"""Add one-time email verification tokens."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0026"
down_revision = "20261104_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
