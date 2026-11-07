"""Business profile of an organization (one per organization)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.organizations import get_membership, require_roles
from app.core.database import get_db
from app.models import BusinessProduct, BusinessProfile, BusinessProfileVersion, IndustryCategory, Membership
from app.modules.audit.activity import record_activity
from app.schemas import (
    BusinessProfileConfirmationResponse, BusinessProfileRequest, BusinessProfileResponse,
    BusinessProfileVersionResponse,
)

router = APIRouter(prefix="/organizations/{organization_id}/profile", tags=["business profile"])


def _validate_categories(db: Session, payload: BusinessProfileRequest) -> None:
    """Make sure the chosen industry/subcategory exist and belong together."""
    if payload.subcategory_id is not None and payload.industry_id is None:
        raise HTTPException(status_code=400, detail="Choose an industry before choosing a subcategory")
    if payload.industry_id is not None:
        industry = db.get(IndustryCategory, payload.industry_id)
        if industry is None or industry.parent_id is not None:
            raise HTTPException(status_code=400, detail="Unknown industry")
    if payload.subcategory_id is not None:
        subcategory = db.get(IndustryCategory, payload.subcategory_id)
        if subcategory is None or subcategory.parent_id != payload.industry_id:
            raise HTTPException(status_code=400, detail="Subcategory does not belong to the chosen industry")


@router.get("", response_model=BusinessProfileResponse)
def get_profile(membership: Membership = Depends(get_membership), db: Session = Depends(get_db)) -> BusinessProfile:
    """Return the organization's business profile to any member; 404 until one is saved."""
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.organization_id == membership.organization_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Business profile has not been set up yet")
    return profile


@router.put("", response_model=BusinessProfileResponse)
def save_profile(
    payload: BusinessProfileRequest,
    membership: Membership = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> BusinessProfile:
    """Create or replace the business profile; restricted to owners and admins."""
    _validate_categories(db, payload)
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.organization_id == membership.organization_id))
    if profile is None:
        profile = BusinessProfile(organization_id=membership.organization_id)
        db.add(profile)
    is_new = profile.id is None
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    profile.profile_version = (profile.profile_version or 0) + 1
    profile.confirmed_at = None  # Any edit requires the user to review and confirm again.
    try:
        db.flush()
        db.add(BusinessProfileVersion(
            organization_id=membership.organization_id,
            version_number=profile.profile_version,
            action="created" if is_new else "updated",
            snapshot={key: (str(value) if value is not None else None) for key, value in payload.model_dump().items()},
            changed_by_user_id=membership.user_id,
        ))
        record_activity(
            db,
            membership,
            "profile.created" if is_new else "profile.updated",
            "business_profile",
            profile.id,
            "Created the business profile" if is_new else "Updated the business profile",
        )
        db.commit()
        db.refresh(profile)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not save the profile. Please try again") from None
    return profile


@router.post("/confirm", response_model=BusinessProfileConfirmationResponse)
def confirm_profile(
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)
) -> dict:
    """Record the user's confirmation of the current business profile."""
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.organization_id == membership.organization_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Business profile has not been set up yet")
    has_structured_products = db.scalar(select(BusinessProduct.id).where(
        BusinessProduct.organization_id == membership.organization_id, BusinessProduct.is_active.is_(True)
    ).limit(1)) is not None
    required = [profile.business_name, profile.niche, profile.description, profile.marketing_goals]
    has_offer = bool(profile.products_services and profile.products_services.strip()) or has_structured_products
    if not all(value and value.strip() for value in required) or not has_offer or profile.industry_id is None:
        raise HTTPException(status_code=409, detail="Complete the required business details before confirming the profile")
    now = datetime.now(timezone.utc)
    profile.confirmed_at = now
    profile.onboarding_completed_at = profile.onboarding_completed_at or now
    db.add(BusinessProfileVersion(
        organization_id=membership.organization_id, version_number=profile.profile_version, action="confirmed",
        snapshot={"business_name": profile.business_name, "industry_id": str(profile.industry_id),
                  "niche": profile.niche, "description": profile.description,
                  "products_services": profile.products_services, "marketing_goals": profile.marketing_goals},
        changed_by_user_id=membership.user_id,
    ))
    record_activity(
        db, membership, "profile.confirmed", "business_profile", profile.id,
        f"Confirmed business profile version {profile.profile_version}",
    )
    db.commit()
    return {"organization_id": membership.organization_id, "profile_version": profile.profile_version,
            "confirmed_at": profile.confirmed_at, "onboarding_completed_at": profile.onboarding_completed_at,
            "message": "Business profile confirmed"}


@router.get("/versions", response_model=list[BusinessProfileVersionResponse])
def list_profile_versions(
    membership: Membership = Depends(get_membership), db: Session = Depends(get_db)
) -> list[BusinessProfileVersion]:
    """List the organization's profile change and confirmation history."""
    return db.scalars(select(BusinessProfileVersion).where(
        BusinessProfileVersion.organization_id == membership.organization_id
    ).order_by(BusinessProfileVersion.created_at.desc(), case((BusinessProfileVersion.action == "confirmed", 0), else_=1), BusinessProfileVersion.version_number.desc()).limit(50)).all()
