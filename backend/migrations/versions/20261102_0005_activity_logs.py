"""Create the organization activity log.

Revision ID: 20261102_0005
Revises: 20261102_0004
Create Date: 2026-11-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0005"
down_revision = "20261102_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("actor_name", sa.String(length=160), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("summary", sa.String(length=400), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_activity_logs_org_created", "activity_logs", ["organization_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_activity_logs_org_created", table_name="activity_logs")
    op.drop_table("activity_logs")
