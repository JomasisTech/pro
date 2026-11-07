"""Add minimal successful login telemetry for platform administration."""
from alembic import op
import sqlalchemy as sa

revision = "20261107_0043"
down_revision = "20261107_0042"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "platform_login_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=32), server_default="password", nullable=False),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_login_events_user_created", "platform_login_events", ["user_id", "created_at"])
    op.create_index("ix_platform_login_events_created", "platform_login_events", ["created_at"])

def downgrade() -> None:
    op.drop_index("ix_platform_login_events_created", table_name="platform_login_events")
    op.drop_index("ix_platform_login_events_user_created", table_name="platform_login_events")
    op.drop_table("platform_login_events")
