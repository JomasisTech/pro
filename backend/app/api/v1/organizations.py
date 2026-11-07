"""Organization endpoints and the reusable tenant-authorization dependencies.

Every future organization-owned endpoint should depend on `get_membership` (any member) or
`require_roles(...)` (specific roles) so access is enforced here on the backend, not in the UI.
"""

import logging
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.v1.auth import get_current_user
from app.config import get_settings
from app.core.database import get_db
from app.core.slug import build_organization_slug
from app.models import (
    ActivityLog,
    BusinessProduct,
    BusinessProfile,
    BusinessProfileVersion,
    CalendarEntry,
    ContentDraft,
    MediaAsset,
    Membership,
    Organization,
    ScheduledPost,
    SocialAccount,
    SocialCredential,
    SocialOAuthState,
    TikTokPublishJob,
    UsageEvent,
    User,
    OrganizationInvitation,
    YouTubePublishJob,
)
from app.modules.audit.activity import record_activity
from app.schemas import (CreateOrganizationRequest, MemberResponse, OrganizationResponse, RenameOrganizationRequest, UpdateMemberRoleRequest, CreateInvitationRequest, InvitationResponse, AcceptInvitationRequest, InvitationAdminResponse)
from app.integrations.email import send_email

router = APIRouter(prefix="/organizations", tags=["organizations"])

log = logging.getLogger(__name__)

# Guards against runaway creation until plans and billing define real limits (set MAX_WORKSPACES_PER_USER).
MAX_ORGANIZATIONS_PER_USER = get_settings().max_workspaces_per_user


def get_membership(
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Membership:
    """Return the caller's membership in the organization from the URL.

    Non-members get 404 (not 403) so the API never reveals whether another tenant's
    organization exists.
    """
    membership = db.scalar(
        select(Membership)
        .where(Membership.user_id == current_user.id, Membership.organization_id == organization_id)
        .options(joinedload(Membership.organization))
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return membership


def require_roles(*allowed_roles: str) -> Callable[..., Membership]:
    """Build a dependency that only lets members with one of `allowed_roles` through."""

    def dependency(membership: Membership = Depends(get_membership)) -> Membership:
        if membership.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        return membership

    return dependency


def _organization_response(membership: Membership) -> OrganizationResponse:
    organization = membership.organization
    return OrganizationResponse(id=organization.id, name=organization.name, slug=organization.slug, role=membership.role)


@router.get("", response_model=list[OrganizationResponse])
def list_my_organizations(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[OrganizationResponse]:
    """List the organizations the signed-in user belongs to."""
    memberships = db.scalars(
        select(Membership)
        .where(Membership.user_id == current_user.id)
        .options(joinedload(Membership.organization))
        .order_by(Membership.created_at)
    ).all()
    return [_organization_response(membership) for membership in memberships]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: CreateOrganizationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """Create a new workspace; the caller becomes its owner."""
    existing_count = db.scalar(select(func.count()).select_from(Membership).where(Membership.user_id == current_user.id))
    if (existing_count or 0) >= MAX_ORGANIZATIONS_PER_USER:
        raise HTTPException(status_code=400, detail="You have reached the maximum number of workspaces")
    organization = Organization(name=payload.name, slug=build_organization_slug(payload.name))
    membership = Membership(user=current_user, organization=organization, role="owner")
    db.add_all([organization, membership])
    try:
        db.flush()
        record_activity(
            db, membership, "organization.created", "organization", organization.id, f'Created workspace "{organization.name}"'
        )
        db.commit()
        db.refresh(membership)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create the workspace. Please try again") from None
    return _organization_response(membership)


@router.get("/{organization_id}", response_model=OrganizationResponse)
def get_organization(membership: Membership = Depends(get_membership)) -> OrganizationResponse:
    """Return one organization, only if the caller is a member."""
    return _organization_response(membership)


@router.get("/{organization_id}/members", response_model=list[MemberResponse])
def list_members(
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)
) -> list[MemberResponse]:
    """List organization members; restricted to owners and admins."""
    members = db.scalars(
        select(Membership)
        .where(Membership.organization_id == membership.organization_id)
        .options(joinedload(Membership.user))
        .order_by(Membership.created_at)
    ).all()
    return [
        MemberResponse(user_id=m.user.id, email=m.user.email, full_name=m.user.full_name, role=m.role)
        for m in members
    ]


@router.patch("/{organization_id}/members/{user_id}", response_model=MemberResponse)
def update_member_role(
    user_id: UUID,
    payload: UpdateMemberRoleRequest,
    membership: Membership = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
) -> MemberResponse:
    """Owners can promote members to admin or change admins back to members.

    Ownership transfer is intentionally excluded from this endpoint.
    """
    target = db.scalar(
        select(Membership).where(
            Membership.organization_id == membership.organization_id,
            Membership.user_id == user_id,
        ).options(joinedload(Membership.user))
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    if target.role == "owner":
        raise HTTPException(status_code=400, detail="Workspace ownership cannot be changed here")
    if target.role != payload.role:
        previous_role = target.role
        target.role = payload.role
        record_activity(
            db, membership, "organization.member_role_changed", "user", target.user_id,
            f'Changed {target.user.email or target.user.full_name} from {previous_role} to {payload.role}',
        )
        db.commit()
        db.refresh(target)
    return MemberResponse(
        user_id=target.user.id, email=target.user.email, full_name=target.user.full_name, role=target.role
    )


@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: UUID,
    membership: Membership = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
) -> Response:
    """Owners can remove non-owner members from the workspace."""
    if user_id == membership.user_id:
        raise HTTPException(status_code=400, detail="You cannot remove yourself as the workspace owner")
    target = db.scalar(
        select(Membership).where(
            Membership.organization_id == membership.organization_id,
            Membership.user_id == user_id,
        ).options(joinedload(Membership.user))
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    if target.role == "owner":
        raise HTTPException(status_code=400, detail="Another owner cannot be removed here")
    record_activity(
        db, membership, "organization.member_removed", "user", target.user_id,
        f'Removed {target.user.email or target.user.full_name} from the workspace',
    )
    db.delete(target)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{organization_id}/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(
    payload: CreateInvitationRequest, background_tasks: BackgroundTasks,
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db),
) -> InvitationResponse:
    """Invite an email address with a single-use token. Admins may invite members only."""
    if membership.role == "admin" and payload.role != "member":
        raise HTTPException(status_code=403, detail="Only the workspace owner can invite an admin")
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user and db.scalar(select(Membership.id).where(
        Membership.organization_id == membership.organization_id, Membership.user_id == existing_user.id
    )):
        raise HTTPException(status_code=409, detail="This person is already a workspace member")
    pending = db.scalar(select(OrganizationInvitation).where(
        OrganizationInvitation.organization_id == membership.organization_id,
        OrganizationInvitation.email == payload.email,
        OrganizationInvitation.accepted_at.is_(None),
        OrganizationInvitation.expires_at > datetime.now(timezone.utc),
    ))
    if pending:
        raise HTTPException(status_code=409, detail="An active invitation already exists for this email")
    raw_token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    invitation = OrganizationInvitation(
        organization_id=membership.organization_id, invited_by_user_id=membership.user_id,
        email=payload.email, role=payload.role, token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=expires, last_sent_at=datetime.now(timezone.utc),
    )
    db.add(invitation)
    record_activity(db, membership, "organization.invitation_created", "organization", membership.organization_id,
                    f'Invited {payload.email} as {payload.role}')
    db.commit()
    settings = get_settings()
    accept_url = f"{settings.frontend_base_url.rstrip('/')}/accept-invitation?token={quote(raw_token)}"
    background_tasks.add_task(send_email, settings, payload.email, f"Invitation to {membership.organization.name}",
        f"You have been invited to join {membership.organization.name} as {payload.role}.\n\nAccept within 7 days: {accept_url}\n\nIf you were not expecting this invitation, ignore this email.")
    return InvitationResponse(email=payload.email, role=payload.role, expires_at=expires,
                              message="Invitation created. Email delivery is attempted in the background.")


@router.get("/{organization_id}/invitations", response_model=list[InvitationAdminResponse])
def list_invitations(
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db),
) -> list[InvitationAdminResponse]:
    """List active and historical invitations for workspace administrators."""
    rows = db.scalars(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.organization_id == membership.organization_id)
        .order_by(OrganizationInvitation.created_at.desc())
        .limit(100)
    ).all()
    return [InvitationAdminResponse.model_validate(row, from_attributes=True) for row in rows]


@router.delete("/{organization_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    invitation_id: UUID,
    membership: Membership = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke a pending invitation; accepted invitations are immutable history."""
    invitation = db.scalar(select(OrganizationInvitation).where(
        OrganizationInvitation.id == invitation_id,
        OrganizationInvitation.organization_id == membership.organization_id,
    ))
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=409, detail="An accepted invitation cannot be revoked")
    if membership.role == "admin" and invitation.role != "member":
        raise HTTPException(status_code=403, detail="Only the workspace owner can manage admin invitations")
    db.delete(invitation)
    record_activity(db, membership, "organization.invitation_revoked", "organization", membership.organization_id,
                    f"Revoked invitation for {invitation.email}")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{organization_id}/invitations/{invitation_id}/resend", response_model=InvitationResponse)
def resend_invitation(
    invitation_id: UUID, background_tasks: BackgroundTasks,
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db),
) -> InvitationResponse:
    """Issue a fresh link (earlier links stop working) and extend the expiry. Expired invitations can be resent."""
    invitation = db.scalar(select(OrganizationInvitation).where(
        OrganizationInvitation.id == invitation_id,
        OrganizationInvitation.organization_id == membership.organization_id,
    ))
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if membership.role == "admin" and invitation.role != "member":
        raise HTTPException(status_code=403, detail="Only the workspace owner can manage admin invitations")
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=409, detail="This invitation has already been accepted")
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if invitation.last_sent_at is not None:
        sent = invitation.last_sent_at if invitation.last_sent_at.tzinfo else invitation.last_sent_at.replace(tzinfo=timezone.utc)
        wait = settings.invitation_resend_cooldown_seconds - (now - sent).total_seconds()
        if wait > 0:
            raise HTTPException(status_code=429, detail="This invitation was sent a moment ago. Please wait before resending",
                                headers={"Retry-After": str(int(wait) + 1)})
    raw_token = secrets.token_urlsafe(32)
    invitation.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    invitation.expires_at = now + timedelta(days=7)
    invitation.last_sent_at = now
    record_activity(db, membership, "organization.invitation_resent", "organization", membership.organization_id,
                    f"Resent invitation to {invitation.email}")
    db.commit()
    accept_url = f"{settings.frontend_base_url.rstrip('/')}/accept-invitation?token={quote(raw_token)}"
    background_tasks.add_task(send_email, settings, invitation.email, f"Invitation to {membership.organization.name}",
        f"You have been invited to join {membership.organization.name} as {invitation.role}.\n\nAccept within 7 days: {accept_url}\n\nIf you were not expecting this invitation, ignore this email.")
    return InvitationResponse(email=invitation.email, role=invitation.role, expires_at=invitation.expires_at,
                              message="Invitation resent. Earlier links no longer work.")


@router.post("/invitations/accept", response_model=OrganizationResponse)
def accept_invitation(
    payload: AcceptInvitationRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> OrganizationResponse:
    """Accept an invitation only when the authenticated account email matches."""
    if not current_user.email:
        raise HTTPException(status_code=400, detail="Add and verify an email address before accepting an invitation")
    digest = hashlib.sha256(payload.token.encode()).hexdigest()
    invitation = db.scalar(select(OrganizationInvitation).where(OrganizationInvitation.token_hash == digest))
    now = datetime.now(timezone.utc)
    if invitation is None or invitation.accepted_at is not None or invitation.expires_at.replace(tzinfo=invitation.expires_at.tzinfo or timezone.utc) <= now:
        raise HTTPException(status_code=400, detail="This invitation is invalid or has expired")
    if current_user.email.lower() != invitation.email.lower():
        raise HTTPException(status_code=403, detail="Sign in with the email address this invitation was sent to")
    existing = db.scalar(select(Membership).where(Membership.organization_id == invitation.organization_id, Membership.user_id == current_user.id))
    if existing is None:
        existing = Membership(user_id=current_user.id, organization_id=invitation.organization_id, role=invitation.role)
        db.add(existing)
    invitation.accepted_at = now
    # The link was delivered to this address, so using it proves the person controls it.
    if current_user.email_verified_at is None:
        current_user.email_verified_at = now
    db.flush()
    record_activity(db, existing, "organization.invitation_accepted", "user", current_user.id,
                    f'Joined workspace {invitation.organization.name} via invitation')
    db.commit()
    db.refresh(existing)
    return _organization_response(existing)


@router.patch("/{organization_id}", response_model=OrganizationResponse)
def rename_organization(
    payload: RenameOrganizationRequest,
    membership: Membership = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """Rename a workspace (owners only). The URL slug is kept stable on purpose."""
    organization = membership.organization
    if payload.name != organization.name:
        previous = organization.name
        organization.name = payload.name
        record_activity(
            db,
            membership,
            "organization.renamed",
            "organization",
            organization.id,
            f'Renamed workspace "{previous}" to "{payload.name}"',
        )
        db.commit()
        db.refresh(membership)
    return _organization_response(membership)


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    confirm_name: str = Query(min_length=1, max_length=160),
    membership: Membership = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
) -> Response:
    """Permanently delete a workspace and everything in it (owners only).

    The caller must type the workspace's exact name, and cannot delete their only workspace.
    The database removes the workspace's records through ON DELETE CASCADE; uploaded media files
    are removed from storage afterwards on a best-effort basis.
    """
    organization = membership.organization
    if confirm_name.strip() != organization.name:
        raise HTTPException(status_code=400, detail="The workspace name you typed does not match")
    membership_count = db.scalar(
        select(func.count()).select_from(Membership).where(Membership.user_id == membership.user_id)
    )
    if (membership_count or 0) <= 1:
        raise HTTPException(status_code=400, detail="You cannot delete your only workspace. Create another one first")
    storage_keys = list(db.scalars(select(MediaAsset.storage_key).where(MediaAsset.organization_id == organization.id)))
    # Explicit deletes (children first) keep this correct on databases, such as SQLite in tests, that do not
    # enforce ON DELETE CASCADE; PostgreSQL would cascade them anyway.
    for model in (
        ScheduledPost, CalendarEntry, TikTokPublishJob, YouTubePublishJob, SocialOAuthState, ContentDraft,
        UsageEvent, ActivityLog, MediaAsset, BusinessProduct, BusinessProfileVersion, BusinessProfile,
    ):
        db.execute(delete(model).where(model.organization_id == organization.id))
    account_ids = list(db.scalars(select(SocialAccount.id).where(SocialAccount.organization_id == organization.id)))
    if account_ids:
        db.execute(delete(SocialCredential).where(SocialCredential.social_account_id.in_(account_ids)))
    db.execute(delete(SocialAccount).where(SocialAccount.organization_id == organization.id))
    db.execute(delete(Membership).where(Membership.organization_id == organization.id))
    db.execute(delete(Organization).where(Organization.id == organization.id))
    db.commit()

    root = Path(get_settings().media_storage_dir).resolve()
    for key in storage_keys:
        try:
            target = (root / key).resolve()
            if root in target.parents:
                target.unlink(missing_ok=True)
        except OSError:
            log.warning("Could not remove media file %s after workspace deletion", key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
