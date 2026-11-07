"""Build a consistent, user-grounded business context for AI features."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BrandIntelligenceAnalysis, BusinessProduct, BusinessProfile, IndustryCategory


def build_business_context(db: Session, organization_id) -> dict | None:
    """Return only user-provided profile facts; social observations are added separately later."""
    profile = db.scalar(
        select(BusinessProfile).where(BusinessProfile.organization_id == organization_id)
    )
    if profile is None:
        return None

    industry = db.get(IndustryCategory, profile.industry_id) if profile.industry_id else None
    approved_analysis = db.scalar(
        select(BrandIntelligenceAnalysis).where(
            BrandIntelligenceAnalysis.organization_id == organization_id,
            BrandIntelligenceAnalysis.status == "approved",
        ).order_by(BrandIntelligenceAnalysis.reviewed_at.desc().nullslast(), BrandIntelligenceAnalysis.created_at.desc()).limit(1)
    )
    products = db.scalars(select(BusinessProduct).where(
        BusinessProduct.organization_id == organization_id, BusinessProduct.is_active.is_(True)
    ).order_by(BusinessProduct.is_primary.desc(), BusinessProduct.created_at)).all()
    required = {
        "business_name": bool(profile.business_name.strip()),
        "industry": industry is not None,
        "niche": bool(profile.niche and profile.niche.strip()),
        "business_description": bool(profile.description and profile.description.strip()),
        "products_or_services": bool((profile.products_services and profile.products_services.strip()) or products),
        "marketing_goals": bool(profile.marketing_goals and profile.marketing_goals.strip()),
    }
    missing = [key for key, present in required.items() if not present]
    completeness = round((sum(required.values()) / len(required)) * 100)

    return {
        "organization_id": profile.organization_id,
        "business_name": profile.business_name,
        "industry": industry.name if industry else None,
        "niche": profile.niche,
        "description": profile.description,
        "location": profile.location,
        "language": profile.language,
        "products_services": profile.products_services,
        "products": [
            {"name": item.name, "description": item.description, "price_amount": item.price_amount,
             "price_currency": item.price_currency, "is_primary": item.is_primary}
            for item in products
        ],
        "target_audience": profile.target_audience,
        "audience_type": profile.audience_type,
        "geographic_market": profile.geographic_market,
        "unique_selling_points": profile.unique_selling_points,
        "marketing_goals": profile.marketing_goals,
        "brand_voice": profile.brand_voice,
        "preferred_tone": profile.preferred_tone,
        "preferred_words": profile.preferred_words,
        "avoided_words": profile.avoided_words,
        "brand_voice_mode": profile.brand_voice_mode or "hybrid",
        "custom_ai_instructions": profile.custom_ai_instructions,
        "learned_brand_voice": (approved_analysis.proposal if approved_analysis else None),
        "completeness_percent": completeness,
        "missing_fields": missing,
        "source": "user_provided",
    }
