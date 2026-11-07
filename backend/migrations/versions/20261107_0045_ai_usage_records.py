"""Track provider-reported AI token usage and optional priced estimates."""
from alembic import op
import sqlalchemy as sa
revision = "20261107_0045"
down_revision = "20261107_0044"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("ai_usage_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("feature", sa.String(length=80), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd_micros", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_ai_usage_records_created_model", "ai_usage_records", ["created_at", "model"])

def downgrade() -> None:
    op.drop_index("ix_ai_usage_records_created_model", table_name="ai_usage_records")
    op.drop_table("ai_usage_records")
