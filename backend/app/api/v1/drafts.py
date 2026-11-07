"""Saved content drafts: create, list, edit, approve/reject, delete. Always scoped to the URL's organization."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.organizations import get_membership
from app.core.database import get_db
from app.models import ContentDraft, Membership, ScheduledPost
from app.modules.audit.activity import record_activity, snippet
from app.schemas import DraftCreateRequest, DraftResponse, DraftStatus, DraftUpdateRequest

router = APIRouter(prefix="/organizations/{organization_id}/drafts", tags=["drafts"])

APPROVER_ROLES = ("owner", "admin")
STATUS_ACTIONS = {
    "approved": ("draft.approved", "Approved"),
    "rejected": ("draft.rejected", "Rejected"),
    "draft": ("draft.reopened", "Moved back to draft:"),
}


def _get_draft(db: Session, membership: Membership, draft_id: UUID) -> ContentDraft:
    """Load a draft only if it belongs to the caller's organization (otherwise 404, never another tenant's)."""
    draft = db.scalar(
        select(ContentDraft).where(
            ContentDraft.id == draft_id, ContentDraft.organization_id == membership.organization_id
        )
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.get("", response_model=list[DraftResponse])
def list_drafts(
    status_filter: DraftStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    membership: Membership = Depends(get_membership),
    db: Session = Depends(get_db),
) -> list[ContentDraft]:
    """Newest first. `limit` (max 100) and `offset` page through results. Any member may read."""
    query = select(ContentDraft).where(ContentDraft.organization_id == membership.organization_id)
    if status_filter is not None:
        query = query.where(ContentDraft.status == status_filter)
    return list(db.scalars(query.order_by(ContentDraft.created_at.desc(), ContentDraft.id).limit(limit).offset(offset)).all())


@router.post("", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
def create_draft(
    payload: DraftCreateRequest, membership: Membership = Depends(get_membership), db: Session = Depends(get_db)
) -> ContentDraft:
    draft = ContentDraft(
        organization_id=membership.organization_id,
        created_by_user_id=membership.user_id,
        content=payload.content,
        topic=payload.topic,
        content_type=payload.content_type,
    )
    db.add(draft)
    db.flush()  # assigns the draft id so the log entry can reference it
    record_activity(db, membership, "draft.created", "draft", draft.id, f'Created draft "{snippet(draft.content)}"')
    db.commit()
    db.refresh(draft)
    return draft


@router.patch("/{draft_id}", response_model=DraftResponse)
def update_draft(
    draft_id: UUID,
    payload: DraftUpdateRequest,
    membership: Membership = Depends(get_membership),
    db: Session = Depends(get_db),
) -> ContentDraft:
    """Edit the text (any member) and/or change status (owners/admins only).

    Editing the text of an approved or rejected draft puts it back to `draft` unless a status is sent too,
    so nobody can approve a caption and then quietly change what was approved.
    """
    if payload.content is None and payload.status is None:
        raise HTTPException(status_code=422, detail="Send content and/or status to update")
    draft = _get_draft(db, membership, draft_id)
    linked_schedule = db.scalar(select(ScheduledPost.id).where(
        ScheduledPost.draft_id == draft.id,
    ).limit(1))
    if linked_schedule and (payload.content is not None or (payload.status is not None and payload.status != draft.status)):
        raise HTTPException(409, detail="This draft has scheduling history and is immutable to preserve the approved content record.")
    if payload.status is not None and payload.status != draft.status and membership.role not in APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="Only owners and admins can approve or reject content")
    if payload.content is not None and payload.content != draft.content:
        draft.content = payload.content
        if payload.status is None:
            draft.status = "draft"
        record_activity(db, membership, "draft.updated", "draft", draft.id, f'Edited draft "{snippet(draft.content)}"')
    if payload.status is not None and payload.status != draft.status:
        draft.status = payload.status
        action, verb = STATUS_ACTIONS[payload.status]
        record_activity(db, membership, action, "draft", draft.id, f'{verb} draft "{snippet(draft.content)}"')
    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(
    draft_id: UUID, membership: Membership = Depends(get_membership), db: Session = Depends(get_db)
) -> Response:
    draft = _get_draft(db, membership, draft_id)
    linked_schedule = db.scalar(select(ScheduledPost.id).where(ScheduledPost.draft_id == draft.id).limit(1))
    if linked_schedule:
        raise HTTPException(409, detail="This draft is linked to a scheduled post and cannot be deleted.")
    if membership.role not in APPROVER_ROLES and draft.created_by_user_id != membership.user_id:
        raise HTTPException(status_code=403, detail="Only the author, owners and admins can delete this draft")
    record_activity(db, membership, "draft.deleted", "draft", draft.id, f'Deleted draft "{snippet(draft.content)}"')
    db.delete(draft)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
