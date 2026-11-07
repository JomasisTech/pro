"""Add profile confirmation/history and structured business products.

Revision ID: 20261102_0007
Revises: 20261102_0006
Create Date: 2026-11-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0007"
down_revision = "20261102_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("business_profiles", sa.Column("profile_version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("business_profiles", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("business_profiles", sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "business_profile_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_business_profile_versions_organization_id", "business_profile_versions", ["organization_id"])
    op.create_table(
        "business_products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_amount", sa.Integer(), nullable=True),
        sa.Column("price_currency", sa.String(length=3), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_business_products_organization_id", "business_products", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_business_products_organization_id", table_name="business_products")
    op.drop_table("business_products")
    op.drop_index("ix_business_profile_versions_organization_id", table_name="business_profile_versions")
    op.drop_table("business_profile_versions")
    op.drop_column("business_profiles", "onboarding_completed_at")
    op.drop_column("business_profiles", "confirmed_at")
    op.drop_column("business_profiles", "profile_version")
