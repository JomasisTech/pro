"""Track when each workspace invitation was last emailed (resend cooldown)."""
from alembic import op
import sqlalchemy as sa

revision = "20261105_0040"
down_revision = "20261104_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organization_invitations", sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("organization_invitations", "last_sent_at")
