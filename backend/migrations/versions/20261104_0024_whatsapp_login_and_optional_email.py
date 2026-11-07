"""WhatsApp one-time-code sign-in: optional email, has_password flag, login code table."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0024"
down_revision = "20261104_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch mode lets SQLite (which cannot ALTER a column in place) run this migration too.
    with op.batch_alter_table("users") as batch:
        batch.alter_column("email", existing_type=sa.String(320), nullable=True)
        batch.add_column(sa.Column("has_password", sa.Boolean(), nullable=False, server_default=sa.true()))
    # Accounts created by Google sign-in hold a random password nobody knows; mark them so the UI does not
    # offer "change password" with a "current password" they cannot supply.
    op.execute(
        "UPDATE users SET has_password = false WHERE id IN "
        "(SELECT user_id FROM auth_identities) AND password_changed_at IS NULL"
    )
    op.create_table(
        "phone_login_codes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_phone_login_codes_phone_e164", "phone_login_codes", ["phone_e164"])


def downgrade() -> None:
    op.drop_index("ix_phone_login_codes_phone_e164", table_name="phone_login_codes")
    op.drop_table("phone_login_codes")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("has_password")
        batch.alter_column("email", existing_type=sa.String(320), nullable=False)
