"""Add delegated platform administrator roles."""
from alembic import op
import sqlalchemy as sa
revision = "20261107_0047"
down_revision = "20261107_0046"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("platform_admin_roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_platform_admin_roles_user"))
    op.create_index("ix_platform_admin_roles_user_id", "platform_admin_roles", ["user_id"])

def downgrade() -> None:
    op.drop_index("ix_platform_admin_roles_user_id", table_name="platform_admin_roles")
    op.drop_table("platform_admin_roles")
