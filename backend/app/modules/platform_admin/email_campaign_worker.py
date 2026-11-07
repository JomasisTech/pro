"""Durable single-instance worker for owner-created platform announcement campaigns."""
from datetime import datetime, timedelta, timezone
import logging
from uuid import uuid4
from sqlalchemy import func, or_, select, update
from app.config import get_settings
from app.core.database import SessionLocal
from app.integrations.email import send_email
from app.integrations.resend_email import send_campaign_email
from app.models import PlatformEmailCampaign, PlatformEmailRecipient, PlatformAdminAudit, PlatformEmailSuppression, PlatformEmailWorkerLease, PlatformEmailProviderEvent

log = logging.getLogger(__name__)

def process_email_campaigns(batch_size: int = 100) -> dict:
    """Durable, restart-safe queue worker. Safe to invoke repeatedly from a scheduler."""
    settings = get_settings()
    db = SessionLocal()
    processed = retried = failed = 0
    owner_token = uuid4().hex
    lease_duration = timedelta(minutes=15)
    try:
        now = datetime.now(timezone.utc)
        # The pre-seeded singleton row is claimed with one conditional UPDATE. This is
        # atomic on supported SQL databases and prevents two schedulers sending together.
        claimed = db.execute(update(PlatformEmailWorkerLease).where(
            PlatformEmailWorkerLease.id == 1,
            PlatformEmailWorkerLease.expires_at <= now,
        ).values(owner_token=owner_token, expires_at=now + lease_duration))
        db.commit()
        if claimed.rowcount != 1:
            return {"processed": 0, "scheduled_retries": 0, "permanently_failed": 0, "skipped": "worker_lease_held"}
        # Process one campaign at a time; recipient rows are committed individually so a
        # worker restart never loses completed deliveries.
        campaign_ids = db.scalars(select(PlatformEmailCampaign.id).where(
            PlatformEmailCampaign.status.in_(["queued", "sending"])
        ).order_by(PlatformEmailCampaign.created_at.asc()).limit(10)).all()
        for campaign_id in campaign_ids:
            campaign = db.get(PlatformEmailCampaign, campaign_id)
            if campaign is None:
                continue
            campaign.status = "sending"
            db.commit()
            recipient_ids = db.scalars(select(PlatformEmailRecipient.id).where(
                PlatformEmailRecipient.campaign_id == campaign_id,
                PlatformEmailRecipient.status.in_(["pending", "retry"]),
                or_(PlatformEmailRecipient.next_attempt_at.is_(None), PlatformEmailRecipient.next_attempt_at <= now)
            ).order_by(PlatformEmailRecipient.id).limit(batch_size)).all()
            for recipient_id in recipient_ids:
                # Renew the global lease between recipients. A crashed process leaves
                # the lease to expire, after which the next scheduler run can recover.
                lease_now = datetime.now(timezone.utc)
                renewed = db.execute(update(PlatformEmailWorkerLease).where(
                    PlatformEmailWorkerLease.id == 1,
                    PlatformEmailWorkerLease.owner_token == owner_token,
                ).values(expires_at=lease_now + lease_duration))
                db.commit()
                if renewed.rowcount != 1:
                    raise RuntimeError("Campaign worker lease was lost; stopping before next recipient")
                recipient = db.get(PlatformEmailRecipient, recipient_id)
                if recipient is None:
                    continue
                suppression = db.scalar(select(PlatformEmailSuppression.id).where(
                    func.lower(PlatformEmailSuppression.email) == recipient.email.strip().casefold()))
                if suppression is not None:
                    recipient.status = "unsubscribed"
                    recipient.error = "Recipient opted out before this campaign delivery attempt"
                    db.commit()
                    continue
                recipient.attempts += 1
                unsubscribe_url = f"{settings.frontend_base_url.rstrip('/')}/email/unsubscribe?token={recipient.unsubscribe_token_hash}"
                body = campaign.body + "\n\n---\nTo stop receiving platform announcement emails, unsubscribe here: " + unsubscribe_url
                if settings.email_campaign_provider.lower() == "resend":
                    send_result = send_campaign_email(
                        settings, to_address=recipient.email, subject=campaign.subject, body=body,
                        idempotency_key=f"platform-campaign/{campaign.id}/recipient/{recipient.id}",
                    )
                    delivered = send_result.accepted
                    recipient.provider_message_id = send_result.provider_message_id or recipient.provider_message_id
                    retryable = send_result.retryable
                    error_message = send_result.error
                else:
                    delivered = send_email(settings, recipient.email, campaign.subject, body, log_body=False)
                    retryable = True
                    error_message = "SMTP did not accept the message"
                processed += 1
                if delivered:
                    recipient.status = "sent"
                    recipient.sent_at = now
                    recipient.error = None
                    campaign.sent_count += 1
                elif retryable and recipient.attempts < 3:
                    recipient.status = "retry"
                    recipient.next_attempt_at = now + timedelta(minutes=2 ** (recipient.attempts + 1))
                    recipient.error = (error_message or "Email provider temporarily rejected the message")[:300]
                    retried += 1
                else:
                    recipient.status = "failed"
                    recipient.error = (error_message or "Email provider delivery failed after three attempts")[:300]
                    campaign.failed_count += 1
                    failed += 1
                db.commit()
                # A provider webhook can arrive before the send response's message ID
                # is committed. Replay any already-recorded event once correlation exists.
                if delivered and recipient.provider_message_id:
                    _apply_recorded_provider_events(db, recipient)
            remaining = db.scalar(select(func.count(PlatformEmailRecipient.id)).where(
                PlatformEmailRecipient.campaign_id == campaign_id,
                PlatformEmailRecipient.status.in_(["pending", "retry"]))) or 0
            if remaining == 0:
                campaign.status = "completed" if campaign.failed_count == 0 else ("completed_with_errors" if campaign.sent_count else "failed")
                campaign.completed_at = datetime.now(timezone.utc)
                db.add(PlatformAdminAudit(actor_user_id=campaign.created_by_user_id, target_user_id=None,
                    action="email_campaign.completed", summary=f"Campaign {campaign.id}: {campaign.sent_count} accepted, {campaign.failed_count} failed"))
            else:
                campaign.status = "sending"
            db.commit()
        return {"processed": processed, "scheduled_retries": retried, "permanently_failed": failed}
    except Exception:
        db.rollback()
        log.exception("Email campaign worker failed")
        raise
    finally:
        try:
            db.execute(update(PlatformEmailWorkerLease).where(
                PlatformEmailWorkerLease.id == 1,
                PlatformEmailWorkerLease.owner_token == owner_token,
            ).values(owner_token=None, expires_at=datetime(1970, 1, 1, tzinfo=timezone.utc)))
            db.commit()
        except Exception:
            db.rollback()
            log.exception("Could not release email campaign worker lease")
        db.close()


def _apply_recorded_provider_events(db, recipient) -> None:
    """Apply webhook events that raced ahead of provider-message-ID persistence."""
    events = db.scalars(select(PlatformEmailProviderEvent).where(
        PlatformEmailProviderEvent.provider_message_id == recipient.provider_message_id,
        PlatformEmailProviderEvent.event_type.in_(["email.delivered", "email.bounced", "email.complained"]),
    ).order_by(PlatformEmailProviderEvent.processed_at.asc())).all()
    for event in events:
        if event.event_type == "email.delivered":
            recipient.status = "delivered"
            recipient.delivered_at = recipient.delivered_at or datetime.now(timezone.utc)
            recipient.error = None
        else:
            recipient.status = "bounced" if event.event_type == "email.bounced" else "unsubscribed"
            recipient.bounced_at = recipient.bounced_at or (datetime.now(timezone.utc) if event.event_type == "email.bounced" else None)
            recipient.error = "Email provider reported a permanent bounce" if event.event_type == "email.bounced" else "Recipient reported this email as spam"
            normalized = recipient.email.strip().casefold()
            exists = db.scalar(select(PlatformEmailSuppression.id).where(func.lower(PlatformEmailSuppression.email) == normalized))
            if exists is None:
                db.add(PlatformEmailSuppression(email=normalized, reason="bounce" if event.event_type == "email.bounced" else "complaint"))
    db.commit()

