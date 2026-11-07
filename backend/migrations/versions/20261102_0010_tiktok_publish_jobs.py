"""Add durable TikTok publish tracking."""
from alembic import op
import sqlalchemy as sa
revision = "20261102_0010"
down_revision = "20261102_0009"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "tiktok_publish_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("publish_id", sa.String(length=100), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("privacy_level", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="upload_pending"),
        sa.Column("provider_status", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("publish_id"),
    )
    op.create_index("ix_tiktok_publish_jobs_organization_id", "tiktok_publish_jobs", ["organization_id"])
    op.create_index("ix_tiktok_publish_jobs_social_account_id", "tiktok_publish_jobs", ["social_account_id"])
    op.create_index("ix_tiktok_publish_jobs_publish_id", "tiktok_publish_jobs", ["publish_id"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_tiktok_publish_jobs_publish_id", table_name="tiktok_publish_jobs")
    op.drop_index("ix_tiktok_publish_jobs_social_account_id", table_name="tiktok_publish_jobs")
    op.drop_index("ix_tiktok_publish_jobs_organization_id", table_name="tiktok_publish_jobs")
    op.drop_table("tiktok_publish_jobs")
