"""Create industry categories (with starter data) and business profiles.

Revision ID: 20261102_0002
Revises: 20261102_0001
Create Date: 2026-11-02
"""
from uuid import NAMESPACE_URL, UUID, uuid5

from alembic import op
import sqlalchemy as sa

revision = "20261102_0002"
down_revision = "20261102_0001"
branch_labels = None
depends_on = None

# Starter industries and subcategories. Edit through future migrations or an admin tool, not in the UI code.
STARTER_CATEGORIES = {
    "fashion": ("Fashion", ["Womenswear", "Menswear", "Accessories", "Tailoring"]),
    "restaurants": ("Restaurants & Food", ["Restaurant", "Cafe", "Bakery", "Catering"]),
    "real-estate": ("Real Estate", ["Sales", "Rentals", "Property Management"]),
    "beauty": ("Beauty & Wellness", ["Salon", "Spa", "Barbershop", "Skincare"]),
    "education": ("Education", ["School", "Tutoring", "Training Provider"]),
    "healthcare": ("Healthcare", ["Clinic", "Pharmacy", "Dental"]),
    "technology": ("Technology", ["Software", "IT Services", "Electronics"]),
    "travel": ("Travel & Hospitality", ["Hotel", "Tours", "Travel Agency"]),
    "retail": ("Retail", ["General Store", "Online Store", "Supermarket"]),
    "professional-services": ("Professional Services", ["Legal", "Accounting", "Consulting", "Marketing Agency"]),
}


def _category_id(slug: str) -> UUID:
    """Deterministic ids so reruns and other environments agree on the same category ids."""
    return uuid5(NAMESPACE_URL, f"autobizpro:category:{slug}")


def upgrade() -> None:
    categories = op.create_table(
        "industry_categories",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("parent_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["industry_categories.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_industry_categories_slug", "industry_categories", ["slug"], unique=True)
    op.create_index("ix_industry_categories_parent_id", "industry_categories", ["parent_id"])

    op.create_table(
        "business_profiles",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("business_name", sa.String(length=160), nullable=False),
        sa.Column("industry_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("subcategory_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("products_services", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("brand_voice", sa.String(length=500), nullable=True),
        sa.Column("language", sa.String(length=35), server_default="en", nullable=False),
        sa.Column("marketing_goals", sa.Text(), nullable=True),
        sa.Column("posting_frequency", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["industry_id"], ["industry_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subcategory_id"], ["industry_categories.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("organization_id", name="uq_business_profile_organization"),
    )
    op.create_index("ix_business_profiles_organization_id", "business_profiles", ["organization_id"])

    industries = []
    subcategories = []
    for order, (slug, (name, subs)) in enumerate(STARTER_CATEGORIES.items()):
        industries.append(
            {"id": _category_id(slug), "slug": slug, "name": name, "parent_id": None, "sort_order": order}
        )
        for sub_order, sub_name in enumerate(subs):
            sub_slug = f"{slug}-{sub_name.lower().replace(' ', '-').replace('&', 'and')}"
            subcategories.append(
                {
                    "id": _category_id(sub_slug),
                    "slug": sub_slug,
                    "name": sub_name,
                    "parent_id": _category_id(slug),
                    "sort_order": sub_order,
                }
            )
    # Parents first so the foreign key is satisfied.
    op.bulk_insert(categories, industries)
    op.bulk_insert(categories, subcategories)


def downgrade() -> None:
    op.drop_index("ix_business_profiles_organization_id", table_name="business_profiles")
    op.drop_table("business_profiles")
    op.drop_index("ix_industry_categories_parent_id", table_name="industry_categories")
    op.drop_index("ix_industry_categories_slug", table_name="industry_categories")
    op.drop_table("industry_categories")
