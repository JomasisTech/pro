"""Add singleton lease for campaign worker coordination."""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = "20261107_0051"
down_revision = "20261107_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_email_worker_leases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_token", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(sa.text("INSERT INTO platform_email_worker_leases (id, owner_token, expires_at) VALUES (1, NULL, '1970-01-01 00:00:00')"))


def downgrade() -> None:
    op.drop_table("platform_email_worker_leases")
