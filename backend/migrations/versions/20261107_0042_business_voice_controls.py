"""Add explicit AI brand-voice source mode and owner instructions."""
from alembic import op
import sqlalchemy as sa

revision = "20261107_0042"
down_revision = "20261105_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "business_profiles",
        sa.Column("brand_voice_mode", sa.String(length=16), nullable=False, server_default="hybrid"),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_ai_instructions", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("business_profiles", "custom_ai_instructions")
    op.drop_column("business_profiles", "brand_voice_mode")
