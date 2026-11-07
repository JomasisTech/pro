"""Link scheduled posts to the approved content draft they publish."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0021"
down_revision = "20261104_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scheduled_posts", sa.Column("draft_id", sa.Uuid(), nullable=True))
    with op.batch_alter_table("scheduled_posts") as batch:
        batch.create_foreign_key(
            "fk_scheduled_posts_draft_id_content_drafts", "content_drafts", ["draft_id"], ["id"], ondelete="RESTRICT"
        )
    op.create_index("ix_scheduled_posts_draft_id", "scheduled_posts", ["draft_id"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_posts_draft_id", table_name="scheduled_posts")
    with op.batch_alter_table("scheduled_posts") as batch:
        batch.drop_constraint("fk_scheduled_posts_draft_id_content_drafts", type_="foreignkey")
    op.drop_column("scheduled_posts", "draft_id")
