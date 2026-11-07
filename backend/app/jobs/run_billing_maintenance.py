"""Single supervised entry point for recurring billing maintenance.

Schedule every five minutes in one managed cron service. Tasks are bounded, emit
structured summaries, and fail the process on an unexpected infrastructure error.
Automatic charges remain independently guarded by BILLING_RENEWALS_ENABLED.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.core.database import SessionLocal
from app.integrations.payments.registry import get_payment_provider
from app.modules.billing.lifecycle import process_subscription_lifecycle
from app.modules.billing.notifications import (
    enqueue_automatic_renewal_activation_notices, enqueue_due_renewal_reminders,
    process_billing_notification_outbox,
)
from app.modules.billing.renewal_reconciliation import reconcile_renewal_attempts
from app.modules.billing.renewals import (
    process_due_subscription_renewals, process_provider_directed_renewal_retries,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("billing_maintenance")


def main() -> int:
    started_at = datetime.now(timezone.utc)
    settings = get_settings()
    summary: dict = {
        "job": "billing_maintenance", "started_at": started_at.isoformat(),
        "automatic_renewals_enabled": settings.billing_renewals_enabled,
        "billing_notifications_enabled": settings.billing_renewal_notifications_enabled,
    }
    try:
        with SessionLocal() as db:
            # Queue and send notices before any renewal charge can be considered.
            if settings.billing_renewal_notifications_enabled:
                summary["activation_notices"] = enqueue_automatic_renewal_activation_notices(db, limit=500)
                summary["renewal_reminders"] = enqueue_due_renewal_reminders(db, limit=100)
                summary["email_delivery"] = process_billing_notification_outbox(db, limit=50)
            else:
                summary["email_delivery"] = {"enabled": False}

            # Reconcile uncertain existing references before considering new due charges.
            summary["renewal_reconciliation"] = reconcile_renewal_attempts(db, limit=50, older_than_minutes=10)

            if settings.billing_renewals_enabled:
                provider = get_payment_provider("paystack", settings)
                summary["provider_directed_retries"] = process_provider_directed_renewal_retries(
                    db, provider=provider, limit=50
                )
                summary["due_renewals"] = process_due_subscription_renewals(db, provider=provider, limit=50)
            else:
                summary["provider_directed_retries"] = {"enabled": False}
                summary["due_renewals"] = {"enabled": False}

            summary["subscription_lifecycle"] = process_subscription_lifecycle(
                db, limit=100, grace_period_days=settings.billing_grace_period_days
            )
        summary["status"] = "ok"
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        log.info(json.dumps(summary, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        summary["status"] = "error"
        summary["error_type"] = type(exc).__name__
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        # Deliberately omit exception text: it may contain provider or connection details.
        log.error(json.dumps(summary, sort_keys=True, default=str))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
