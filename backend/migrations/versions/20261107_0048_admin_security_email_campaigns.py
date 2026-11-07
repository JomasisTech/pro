"""Add admin security telemetry and owner email campaigns."""
from alembic import op
import sqlalchemy as sa
revision = "20261107_0048"
down_revision = "20261107_0047"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("platform_login_events", sa.Column("ip_address", sa.String(64), nullable=True))
    op.add_column("platform_login_events", sa.Column("success", sa.Boolean(), server_default=sa.true(), nullable=False))
    # Match the model's standalone created_at index.
    op.create_index("ix_platform_login_events_created_at", "platform_login_events", ["created_at"])
    op.create_table("platform_email_campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(180), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), server_default="queued", nullable=False),
        sa.Column("recipient_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_table("platform_email_recipients",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True), sa.Column("email", sa.String(320), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("error", sa.String(300), nullable=True), sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["platform_email_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_platform_email_recipients_campaign_id", "platform_email_recipients", ["campaign_id"])

def downgrade() -> None:
    op.drop_index("ix_platform_email_recipients_campaign_id", table_name="platform_email_recipients")
    op.drop_table("platform_email_recipients"); op.drop_table("platform_email_campaigns")
    op.drop_index("ix_platform_login_events_created_at", table_name="platform_login_events")
    op.drop_column("platform_login_events", "success"); op.drop_column("platform_login_events", "ip_address")
