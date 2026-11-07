"""Local demo mode: a ready-made account and sample data so the whole app can be explored without setup.

Enabled with DEMO_MODE=true (refused in production by app/config.py). On startup it:
  1. creates the database tables in the isolated SQLite demo database,
  2. adds the industry categories and billing prices that the migrations normally seed,
  3. creates separate customer and platform-owner demo identities, each with an isolated workspace.
It is idempotent: running it again never duplicates data, and it resets the demo password to DEMO_PASSWORD.
"""

import logging
import secrets
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.core.slug import build_organization_slug

log = logging.getLogger(__name__)

_CATEGORIES: dict[str, tuple[str, list[str]]] = {
    "restaurants": ("Restaurants & Food", ["Restaurant", "Cafe", "Bakery", "Catering"]),
    "beauty": ("Beauty & Wellness", ["Salon", "Spa", "Barbershop", "Skincare"]),
    "retail": ("Retail", ["General Store", "Online Store", "Supermarket"]),
    "technology": ("Technology", ["Software", "IT Services", "Electronics"]),
    "professional-services": ("Professional Services", ["Legal", "Accounting", "Consulting", "Marketing Agency"]),
}

_PRICES = {
    ("standard", "NGN", "monthly"): 750000, ("premium", "NGN", "monthly"): 1500000,
    ("standard", "USD", "monthly"): 999, ("premium", "USD", "monthly"): 1999,
    ("standard", "NGN", "annual"): 7500000, ("premium", "NGN", "annual"): 15000000,
    ("standard", "USD", "annual"): 9990, ("premium", "USD", "annual"): 19990,
}


def _category_id(slug: str):
    # Same deterministic ids as the Alembic migration, so demo and real databases agree.
    return uuid5(NAMESPACE_URL, f"autobizpro:category:{slug}")


def _seed_categories(db: Session) -> None:
    from app.models import IndustryCategory

    if db.scalar(select(IndustryCategory.id).limit(1)) is not None:
        return
    for order, (slug, (name, subs)) in enumerate(_CATEGORIES.items()):
        db.add(IndustryCategory(id=_category_id(slug), slug=slug, name=name, parent_id=None, sort_order=order))
    db.flush()  # parents first so the foreign key is satisfied
    for slug, (_name, subs) in _CATEGORIES.items():
        for sub_order, sub_name in enumerate(subs):
            sub_slug = f"{slug}-{sub_name.lower().replace(' ', '-').replace('&', 'and')}"
            db.add(IndustryCategory(id=_category_id(sub_slug), slug=sub_slug, name=sub_name,
                                    parent_id=_category_id(slug), sort_order=sub_order))


def _seed_prices(db: Session) -> None:
    from app.models import BillingPrice

    if db.scalar(select(BillingPrice.id).limit(1)) is not None:
        return
    for (plan, currency, interval), amount in _PRICES.items():
        db.add(BillingPrice(plan_id=plan, currency=currency, billing_interval=interval,
                            amount_minor=amount, enabled=True))


def _seed_demo_account(db: Session) -> None:
    from app.models import BusinessProfile, Membership, Organization, User

    settings = get_settings()
    email = settings.demo_email.strip().lower()
    now = datetime.now(timezone.utc)

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, full_name=settings.demo_full_name, password_hash=hash_password(settings.demo_password),
                    has_password=True, is_active=True, email_verified_at=now)
        db.add(user)
    else:
        # Keep the demo login working even if the password was changed or the account was disabled.
        user.password_hash = hash_password(settings.demo_password)
        user.has_password = True
        user.is_active = True
        user.email_verified_at = user.email_verified_at or now
    db.flush()

    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).limit(1))
    if membership is None:
        organization = Organization(name=settings.demo_organization_name,
                                    slug=build_organization_slug(settings.demo_organization_name), plan="premium")
        db.add(organization)
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=organization.id, role="owner"))
    else:
        organization = db.get(Organization, membership.organization_id)
    db.flush()

    if db.scalar(select(BusinessProfile.id).where(BusinessProfile.organization_id == organization.id)) is None:
        db.add(BusinessProfile(
            organization_id=organization.id, business_name=settings.demo_organization_name,
            industry_id=_category_id("retail"), niche="Handmade gifts",
            description="A small demo shop used to explore AutoBizPro.",
            products_services="Gift boxes, candles, custom stationery",
            location="Lagos, Nigeria", target_audience="Young professionals shopping for thoughtful gifts",
            audience_type="consumers", brand_voice="Warm, friendly and practical", preferred_tone="Friendly",
            marketing_goals="Grow Instagram followers and drive weekend orders", posting_frequency="3 per week",
            confirmed_at=now, onboarding_completed_at=now,
        ))



def _seed_demo_admin_account(db: Session) -> None:
    """Seed a distinct platform-owner identity so customer demo tokens never inherit admin access."""
    from app.models import Membership, Organization, User

    settings = get_settings()
    email = settings.demo_admin_email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email, full_name=settings.demo_admin_full_name,
            password_hash=hash_password(secrets.token_urlsafe(48)), has_password=False,
            is_active=True, email_verified_at=datetime.now(timezone.utc),
        )
        db.add(user)
    else:
        user.full_name = settings.demo_admin_full_name
        # The owner demo can only be entered through /admin/login, never by reusing the
        # customer demo password on the ordinary /login route.
        user.password_hash = hash_password(secrets.token_urlsafe(48))
        user.has_password = False
        user.is_active = True
        user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
    db.flush()

    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).limit(1))
    if membership is None:
        organization = Organization(
            name="Platform Owner Demo Workspace",
            slug=build_organization_slug("Platform Owner Demo Workspace"), plan="premium",
        )
        db.add(organization)
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=organization.id, role="owner"))


def prepare_demo_environment() -> None:
    """Create tables (SQLite only), seed reference data, and make sure the demo account exists."""
    settings = get_settings()
    import app.models  # noqa: F401  (registers every table on Base.metadata)

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
    with SessionLocal() as db:
        _seed_categories(db)
        _seed_prices(db)
        _seed_demo_account(db)
        _seed_demo_admin_account(db)
        db.commit()
    log.warning("DEMO MODE is ON: customer demo %s; administrator demo %s. Never enable this in production.",
                settings.demo_email, settings.demo_admin_email)


def is_demo_platform_admin(user, settings=None) -> bool:
    """Return true only for the seeded demo identity on an explicitly demo-enabled server."""
    settings = settings or get_settings()
    return bool(
        getattr(settings, "demo_mode", False)
        and user.email
        and user.email.casefold() == getattr(settings, "demo_admin_email", "").strip().casefold()
        and user.email_verified_at is not None
        and user.is_active
    )
