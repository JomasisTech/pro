"""Writes activity-log entries. Call it inside the same request/transaction as the change it describes."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ActivityLog, Membership


def snippet(text: str | None, length: int = 60) -> str:
    """A short single-line preview of user text for log summaries."""
    cleaned = " ".join((text or "").split())
    return cleaned if len(cleaned) <= length else cleaned[: length - 1].rstrip() + "…"


def record_activity(
    db: Session,
    membership: Membership,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    summary: str,
) -> None:
    """Add a log entry to the session WITHOUT committing, so it is saved atomically with the change itself.

    If the change fails and is rolled back, the log entry is rolled back too.
    """
    db.add(
        ActivityLog(
            organization_id=membership.organization_id,
            actor_user_id=membership.user_id,
            actor_name=membership.user.full_name,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary[:400],
        )
    )


def record_user_event(db: Session, user, action: str, summary: str, *, only_first_membership: bool = False) -> None:
    """Log a user-level event (registration, sign-in) in the workspaces the person belongs to, then commit.

    Activity logs belong to a workspace, so a sign-in is written to each workspace the user is a member of
    (capped by the per-user workspace limit). Failed sign-ins are not logged: there is no verified user,
    and therefore no workspace, to attach them to. Logging problems never block the sign-in itself.
    """
    import logging

    from sqlalchemy import select
    from sqlalchemy.exc import SQLAlchemyError

    try:
        memberships = db.scalars(
            select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)
        ).all()
        if only_first_membership:
            memberships = memberships[:1]
        for membership in memberships:
            db.add(
                ActivityLog(
                    organization_id=membership.organization_id,
                    actor_user_id=user.id,
                    actor_name=user.full_name,
                    action=action,
                    entity_type="user",
                    entity_id=user.id,
                    summary=summary[:400],
                )
            )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logging.getLogger(__name__).warning("Could not record %s activity", action, exc_info=True)
