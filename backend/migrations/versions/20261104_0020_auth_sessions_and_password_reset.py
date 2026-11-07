"""Session revocation, user token version, and password-reset tokens."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0020"
down_revision = "20261102_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_version", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])
    op.create_index("ix_revoked_tokens_user_id", "revoked_tokens", ["user_id"])
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_revoked_tokens_user_id", table_name="revoked_tokens")
    op.drop_index("ix_revoked_tokens_expires_at", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "token_version")
