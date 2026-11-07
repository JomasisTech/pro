"""Queue and deliver billing notices through the durable SMTP outbox.

Run from backend/: python -m app.jobs.process_billing_notifications
Schedule daily (or every few hours) before the renewal worker. SMTP delivery is retried
with bounded backoff; BILLING_RENEWAL_NOTIFICATIONS_ENABLED defaults to false.
"""
import json

from app.config import get_settings
from app.core.database import SessionLocal
from app.modules.billing.notifications import (
    enqueue_automatic_renewal_activation_notices, enqueue_due_renewal_reminders,
    process_billing_notification_outbox,
)


def main() -> int:
    settings = get_settings()
    if not settings.billing_renewal_notifications_enabled:
        print(json.dumps({"enabled": False, "message": "Billing notifications are disabled"}, sort_keys=True))
        return 0
    with SessionLocal() as db:
        activation_notices = enqueue_automatic_renewal_activation_notices(db, limit=500)
        reminders = enqueue_due_renewal_reminders(db, limit=100)
        delivery = process_billing_notification_outbox(db, limit=50)
    print(json.dumps({"enabled": True, "activation_notices": activation_notices, "reminders": reminders, "delivery": delivery}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
