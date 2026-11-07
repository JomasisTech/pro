"""CLI entry point for scheduled Paystack payment reconciliation.

Run from the backend directory with:
    python -m app.jobs.reconcile_payments
A hosting cron/scheduler can invoke this command every 5-10 minutes.
"""
import json

from app.core.database import SessionLocal
from app.modules.billing.reconciliation import reconcile_pending_payments


def main() -> int:
    with SessionLocal() as db:
        result = reconcile_pending_payments(db, limit=50, older_than_minutes=10)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["provider_unavailable"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
