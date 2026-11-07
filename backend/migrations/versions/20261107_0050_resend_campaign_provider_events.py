"""Add idempotent Resend campaign event ledger."""
from alembic import op
import sqlalchemy as sa

revision = "20261107_0050"
down_revision = "20261107_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_email_provider_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=24), server_default="resend", nullable=False),
        sa.Column("provider_event_id", sa.String(length=200), nullable=False),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_event_id"),
    )
    op.create_index("ix_platform_email_provider_events_provider_event_id", "platform_email_provider_events", ["provider_event_id"], unique=True)
    op.create_index("ix_platform_email_provider_events_provider_message_id", "platform_email_provider_events", ["provider_message_id"])


def downgrade() -> None:
    op.drop_index("ix_platform_email_provider_events_provider_message_id", table_name="platform_email_provider_events")
    op.drop_index("ix_platform_email_provider_events_provider_event_id", table_name="platform_email_provider_events")
    op.drop_table("platform_email_provider_events")
