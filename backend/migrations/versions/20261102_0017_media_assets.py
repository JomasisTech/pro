"""Add private organization-owned media assets."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261102_0017"
down_revision = "20261102_0016"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("media_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("storage_key"))
    op.create_index("ix_media_assets_organization_id", "media_assets", ["organization_id"])

def downgrade() -> None:
    op.drop_index("ix_media_assets_organization_id", table_name="media_assets")
    op.drop_table("media_assets")
