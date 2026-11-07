"""Add provider-backed unified calendar entries."""
from alembic import op
import sqlalchemy as sa
revision = "20261102_0013"
down_revision = "20261102_0012"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("calendar_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("external_post_id", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="scheduled", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_calendar_entries_organization_id", "calendar_entries", ["organization_id"])
    op.create_index("ix_calendar_entries_social_account_id", "calendar_entries", ["social_account_id"])
    op.create_index("ix_calendar_entries_org_scheduled", "calendar_entries", ["organization_id", "scheduled_at"])

def downgrade() -> None:
    op.drop_index("ix_calendar_entries_org_scheduled", table_name="calendar_entries")
    op.drop_index("ix_calendar_entries_social_account_id", table_name="calendar_entries")
    op.drop_index("ix_calendar_entries_organization_id", table_name="calendar_entries")
    op.drop_table("calendar_entries")
