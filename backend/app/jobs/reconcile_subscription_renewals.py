"""Verification-only recovery for interrupted subscription renewal attempts.

Run from backend/: python -m app.jobs.reconcile_subscription_renewals
This job never charges a saved authorization. It verifies existing references only.
"""
import json

from app.core.database import SessionLocal
from app.modules.billing.renewal_reconciliation import reconcile_renewal_attempts


def main() -> int:
    with SessionLocal() as db:
        result = reconcile_renewal_attempts(db, limit=50, older_than_minutes=10)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
