"""Organization-scoped structured products and services management."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.organizations import get_membership, require_roles
from app.core.database import get_db
from app.models import BusinessProduct, Membership
from app.modules.audit.activity import record_activity
from app.schemas import BusinessProductCreateRequest, BusinessProductResponse, BusinessProductUpdateRequest

router = APIRouter(prefix="/organizations/{organization_id}/products", tags=["business products and services"])


def _owned_product(db: Session, organization_id: UUID, product_id: UUID) -> BusinessProduct:
    product = db.scalar(select(BusinessProduct).where(
        BusinessProduct.id == product_id, BusinessProduct.organization_id == organization_id
    ))
    if product is None:
        raise HTTPException(status_code=404, detail="Product or service not found")
    return product


@router.get("", response_model=list[BusinessProductResponse])
def list_products(membership: Membership = Depends(get_membership), db: Session = Depends(get_db)):
    return db.scalars(select(BusinessProduct).where(
        BusinessProduct.organization_id == membership.organization_id
    ).order_by(BusinessProduct.is_primary.desc(), BusinessProduct.created_at)).all()


@router.post("", response_model=BusinessProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(payload: BusinessProductCreateRequest, membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    if payload.is_primary:
        previous_primaries = db.scalars(select(BusinessProduct).where(
            BusinessProduct.organization_id == membership.organization_id,
            BusinessProduct.is_primary.is_(True),
        )).all()
        for previous in previous_primaries:
            previous.is_primary = False
            record_activity(
                db, membership, "business_product.primary_changed", "business_product", previous.id,
                f'Removed primary designation from "{previous.name[:60]}"',
            )
    product = BusinessProduct(organization_id=membership.organization_id, **payload.model_dump())
    db.add(product)
    db.flush()
    record_activity(
        db, membership, "business_product.created", "business_product", product.id,
        f'Created product or service "{product.name[:60]}"',
    )
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=BusinessProductResponse)
def update_product(product_id: UUID, payload: BusinessProductUpdateRequest, membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    product = _owned_product(db, membership.organization_id, product_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("is_primary") is True:
        previous_primaries = db.scalars(select(BusinessProduct).where(
            BusinessProduct.organization_id == membership.organization_id,
            BusinessProduct.id != product_id,
            BusinessProduct.is_primary.is_(True),
        )).all()
        for previous in previous_primaries:
            previous.is_primary = False
            record_activity(
                db, membership, "business_product.primary_changed", "business_product", previous.id,
                f'Removed primary designation from "{previous.name[:60]}"',
            )
    changed = {key: value for key, value in changes.items() if getattr(product, key) != value}
    for key, value in changed.items():
        setattr(product, key, value)
    if changed:
        record_activity(
            db, membership, "business_product.updated", "business_product", product.id,
            f'Updated product or service "{product.name[:60]}" ({", ".join(sorted(changed))})',
        )
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: UUID, membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)) -> None:
    product = _owned_product(db, membership.organization_id, product_id)
    record_activity(
        db, membership, "business_product.deleted", "business_product", product.id,
        f'Deleted product or service "{product.name[:60]}"',
    )
    db.delete(product)
    db.commit()
