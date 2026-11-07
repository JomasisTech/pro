"""Scheduled subscription expiry/grace-period processor.

Run from backend/: python -m app.jobs.process_subscription_lifecycle
Schedule every 15-60 minutes. This job never initiates a payment or silently renews a plan.
"""
import json

from app.core.database import SessionLocal
from app.config import get_settings
from app.modules.billing.lifecycle import process_subscription_lifecycle


def main() -> int:
    with SessionLocal() as db:
        result = process_subscription_lifecycle(db, limit=100, grace_period_days=get_settings().billing_grace_period_days)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
