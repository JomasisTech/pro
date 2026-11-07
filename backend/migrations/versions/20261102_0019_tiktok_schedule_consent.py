"""Persist explicit TikTok scheduled-upload consent."""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0019"
down_revision = "20261102_0018"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("scheduled_posts", sa.Column("consent_to_upload", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("scheduled_posts", sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scheduled_posts", sa.Column("consent_version", sa.String(length=32), nullable=True))

def downgrade() -> None:
    op.drop_column("scheduled_posts", "consent_version")
    op.drop_column("scheduled_posts", "consented_at")
    op.drop_column("scheduled_posts", "consent_to_upload")
