"""Opt-in scheduled Paystack subscription renewal processor.

Run from backend/: python -m app.jobs.process_subscription_renewals
Configure a single scheduler instance initially. Set BILLING_RENEWALS_ENABLED=true
only after test-mode checkout, webhook, encryption-key backup and customer notices
have been validated. Each subscription period is charged at most once.
"""
import json

from app.config import get_settings
from app.core.database import SessionLocal
from app.integrations.payments.registry import get_payment_provider
from app.modules.billing.renewals import (
    process_due_subscription_renewals, process_provider_directed_renewal_retries,
)


def main() -> int:
    settings = get_settings()
    if not settings.billing_renewals_enabled:
        print(json.dumps({"enabled": False, "message": "Automatic renewals are disabled"}, sort_keys=True))
        return 0
    provider = get_payment_provider("paystack", settings)
    with SessionLocal() as db:
        retries = process_provider_directed_renewal_retries(db, provider=provider, limit=50)
        result = process_due_subscription_renewals(db, provider=provider, limit=50)
    print(json.dumps({"provider_directed_retries": retries, "due_renewals": result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
