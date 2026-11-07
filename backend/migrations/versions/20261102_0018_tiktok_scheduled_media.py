"""Add stored-video and provider tracking fields for TikTok schedules."""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0018"
down_revision = "20261102_0017"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("scheduled_posts", sa.Column("media_asset_id", sa.Uuid(), nullable=True))
    op.add_column("scheduled_posts", sa.Column("video_duration_seconds", sa.Integer(), nullable=True))
    op.add_column("scheduled_posts", sa.Column("privacy_level", sa.String(length=40), nullable=True))
    op.add_column("scheduled_posts", sa.Column("allow_comment", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("scheduled_posts", sa.Column("allow_duet", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("scheduled_posts", sa.Column("allow_stitch", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("scheduled_posts", sa.Column("provider_publish_id", sa.String(length=100), nullable=True))
    with op.batch_alter_table("scheduled_posts") as batch:
        batch.create_foreign_key("fk_scheduled_posts_media_asset_id_media_assets", "media_assets", ["media_asset_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_scheduled_posts_media_asset_id", "scheduled_posts", ["media_asset_id"])
    op.create_index("ix_scheduled_posts_provider_publish_id", "scheduled_posts", ["provider_publish_id"])

def downgrade() -> None:
    op.drop_index("ix_scheduled_posts_provider_publish_id", table_name="scheduled_posts")
    op.drop_index("ix_scheduled_posts_media_asset_id", table_name="scheduled_posts")
    with op.batch_alter_table("scheduled_posts") as batch:
        batch.drop_constraint("fk_scheduled_posts_media_asset_id_media_assets", type_="foreignkey")
        for name in ("provider_publish_id", "allow_stitch", "allow_duet", "allow_comment", "privacy_level", "video_duration_seconds", "media_asset_id"):
            batch.drop_column(name)
