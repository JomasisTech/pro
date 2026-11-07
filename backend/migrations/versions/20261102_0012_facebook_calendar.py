"""Facebook Page publishing integration (uses existing social credential tables)."""
from alembic import op
revision = "20261102_0012"
down_revision = "20261102_0011"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # No schema change: Page tokens and account metadata reuse the encrypted
    # SocialCredential and SocialAccount tables; calendar initially aggregates drafts.
    pass

def downgrade() -> None:
    pass
