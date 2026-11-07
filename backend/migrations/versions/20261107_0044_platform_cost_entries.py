"""Add verified manual operating cost ledger for platform finance reporting."""
from alembic import op
import sqlalchemy as sa
revision = "20261107_0044"
down_revision = "20261107_0043"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("platform_cost_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_platform_cost_entries_period_currency", "platform_cost_entries", ["period_start", "currency"])

def downgrade() -> None:
    op.drop_index("ix_platform_cost_entries_period_currency", table_name="platform_cost_entries")
    op.drop_table("platform_cost_entries")
