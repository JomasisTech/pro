"""Add durable campaign retry state and global email suppression."""
from alembic import op
import sqlalchemy as sa

revision = "20261107_0049"
down_revision = "20261107_0048"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("platform_email_recipients", sa.Column("attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("platform_email_recipients", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("platform_email_recipients", sa.Column("provider_message_id", sa.String(200), nullable=True))
    op.add_column("platform_email_recipients", sa.Column("unsubscribe_token_hash", sa.String(64), nullable=True))
    op.add_column("platform_email_recipients", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("platform_email_recipients", sa.Column("bounced_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_platform_email_recipients_unsubscribe_token_hash", "platform_email_recipients", ["unsubscribe_token_hash"], unique=True)
    op.create_table("platform_email_suppressions",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("email", sa.String(320), nullable=False),
        sa.Column("reason", sa.String(24), nullable=False, server_default="unsubscribe"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("email"))
    op.create_index("ix_platform_email_suppressions_email", "platform_email_suppressions", ["email"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_platform_email_suppressions_email", table_name="platform_email_suppressions")
    op.drop_table("platform_email_suppressions")
    op.drop_index("ix_platform_email_recipients_unsubscribe_token_hash", table_name="platform_email_recipients")
    for column in ["bounced_at", "delivered_at", "unsubscribe_token_hash", "provider_message_id", "next_attempt_at", "attempts"]:
        op.drop_column("platform_email_recipients", column)
