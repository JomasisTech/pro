"""Expand business profiles for structured onboarding context.

Revision ID: 20261102_0006
Revises: 20261102_0005
Create Date: 2026-11-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0006"
down_revision = "20261102_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("business_profiles", sa.Column("niche", sa.String(length=160), nullable=True))
    op.add_column("business_profiles", sa.Column("audience_type", sa.String(length=40), nullable=True))
    op.add_column("business_profiles", sa.Column("geographic_market", sa.String(length=160), nullable=True))
    op.add_column("business_profiles", sa.Column("unique_selling_points", sa.Text(), nullable=True))
    op.add_column("business_profiles", sa.Column("preferred_tone", sa.String(length=120), nullable=True))
    op.add_column("business_profiles", sa.Column("preferred_words", sa.Text(), nullable=True))
    op.add_column("business_profiles", sa.Column("avoided_words", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("business_profiles", "avoided_words")
    op.drop_column("business_profiles", "preferred_words")
    op.drop_column("business_profiles", "preferred_tone")
    op.drop_column("business_profiles", "unique_selling_points")
    op.drop_column("business_profiles", "geographic_market")
    op.drop_column("business_profiles", "audience_type")
    op.drop_column("business_profiles", "niche")
