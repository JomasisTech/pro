"""Add provider-neutral durable scheduled posts."""
from alembic import op
import sqlalchemy as sa
revision = "20261102_0014"
down_revision = "20261102_0013"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("scheduled_posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("link_url", sa.String(2048), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("external_post_id", sa.String(240), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_scheduled_posts_due", "scheduled_posts", ["status", "scheduled_at"])
    op.create_index("ix_scheduled_posts_org", "scheduled_posts", ["organization_id", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_scheduled_posts_org", table_name="scheduled_posts")
    op.drop_index("ix_scheduled_posts_due", table_name="scheduled_posts")
    op.drop_table("scheduled_posts")
