"""Add public media URL support for Instagram photo scheduling."""
from alembic import op
import sqlalchemy as sa

revision = "20261102_0015"
down_revision = "20261102_0014"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("scheduled_posts", sa.Column("media_url", sa.String(length=2048), nullable=True))

def downgrade() -> None:
    op.drop_column("scheduled_posts", "media_url")
