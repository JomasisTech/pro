"""Add durable Brand Intelligence synchronization jobs."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0028"
down_revision = "20261104_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brand_sync_jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("social_account_id", sa.Uuid(as_uuid=True), sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_brand_sync_jobs_organization_id", "brand_sync_jobs", ["organization_id"])
    op.create_index("ix_brand_sync_jobs_social_account_id", "brand_sync_jobs", ["social_account_id"])
    op.create_index("ix_brand_sync_jobs_status", "brand_sync_jobs", ["status"])
    op.create_index("ix_brand_sync_jobs_available_at", "brand_sync_jobs", ["available_at"])


def downgrade() -> None:
    op.drop_index("ix_brand_sync_jobs_available_at", table_name="brand_sync_jobs")
    op.drop_index("ix_brand_sync_jobs_status", table_name="brand_sync_jobs")
    op.drop_index("ix_brand_sync_jobs_social_account_id", table_name="brand_sync_jobs")
    op.drop_index("ix_brand_sync_jobs_organization_id", table_name="brand_sync_jobs")
    op.drop_table("brand_sync_jobs")
