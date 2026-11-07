"""Add append-only audit records for platform administration."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0032"
down_revision = "20261104_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_admin_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=400), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_admin_audits_actor_user_id", "platform_admin_audits", ["actor_user_id"])
    op.create_index("ix_platform_admin_audits_target_user_id", "platform_admin_audits", ["target_user_id"])
    op.create_index("ix_platform_admin_audits_created_at", "platform_admin_audits", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_platform_admin_audits_created_at", table_name="platform_admin_audits")
    op.drop_index("ix_platform_admin_audits_target_user_id", table_name="platform_admin_audits")
    op.drop_index("ix_platform_admin_audits_actor_user_id", table_name="platform_admin_audits")
    op.drop_table("platform_admin_audits")
