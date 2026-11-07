"""Add provenance-backed social observations and reviewable brand proposals."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0027"
down_revision = "20261104_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "social_post_observations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("social_account_id", sa.Uuid(as_uuid=True), sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("source_post_id", sa.String(200), nullable=False),
        sa.Column("post_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("permalink", sa.String(1000), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("social_account_id", "source_post_id", name="uq_social_observation_source_post"),
    )
    op.create_index("ix_social_post_observations_organization_id", "social_post_observations", ["organization_id"])
    op.create_index("ix_social_post_observations_social_account_id", "social_post_observations", ["social_account_id"])
    op.create_table(
        "brand_intelligence_analyses",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("proposal", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("conflicts", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source_observation_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_brand_intelligence_analyses_organization_id", "brand_intelligence_analyses", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_brand_intelligence_analyses_organization_id", table_name="brand_intelligence_analyses")
    op.drop_table("brand_intelligence_analyses")
    op.drop_index("ix_social_post_observations_social_account_id", table_name="social_post_observations")
    op.drop_index("ix_social_post_observations_organization_id", table_name="social_post_observations")
    op.drop_table("social_post_observations")
