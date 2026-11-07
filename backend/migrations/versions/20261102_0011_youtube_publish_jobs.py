"""Add YouTube resumable publishing jobs."""
from alembic import op
import sqlalchemy as sa
revision = "20261102_0011"
down_revision = "20261102_0010"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "youtube_publish_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.String(length=32), nullable=True),
        sa.Column("upload_session_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("privacy_status", sa.String(length=16), nullable=False, server_default="private"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="upload_pending"),
        sa.Column("failure_reason", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_youtube_publish_jobs_organization_id", "youtube_publish_jobs", ["organization_id"])
    op.create_index("ix_youtube_publish_jobs_social_account_id", "youtube_publish_jobs", ["social_account_id"])
    op.create_index("ix_youtube_publish_jobs_video_id", "youtube_publish_jobs", ["video_id"])

def downgrade() -> None:
    op.drop_index("ix_youtube_publish_jobs_video_id", table_name="youtube_publish_jobs")
    op.drop_index("ix_youtube_publish_jobs_social_account_id", table_name="youtube_publish_jobs")
    op.drop_index("ix_youtube_publish_jobs_organization_id", table_name="youtube_publish_jobs")
    op.drop_table("youtube_publish_jobs")
