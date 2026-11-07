"""Create content drafts.

Revision ID: 20261102_0004
Revises: 20261102_0003
Create Date: 2026-11-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0004"
down_revision = "20261102_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_drafts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=300), nullable=True),
        sa.Column("content_type", sa.String(length=32), server_default="general", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_content_drafts_org_created", "content_drafts", ["organization_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_content_drafts_org_created", table_name="content_drafts")
    op.drop_table("content_drafts")
