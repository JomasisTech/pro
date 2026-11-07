"""Add staged TOTP authenticator enrollment fields to users."""
from alembic import op
import sqlalchemy as sa

revision = "20261105_0041"
down_revision = "20261105_0040"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("totp_pending_secret", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade() -> None:
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_pending_secret")
    op.drop_column("users", "totp_secret")
