"""Add organization plan and usage events.

Revision ID: 20261102_0003
Revises: 20261102_0002
Create Date: 2026-11-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0003"
down_revision = "20261102_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("plan", sa.String(length=32), server_default="free", nullable=False))
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_usage_events_org_metric_created", "usage_events", ["organization_id", "metric", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_usage_events_org_metric_created", table_name="usage_events")
    op.drop_table("usage_events")
    op.drop_column("organizations", "plan")
