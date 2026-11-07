"""Check billing scheduler prerequisites; optionally send one controlled SMTP test email."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import text

from app.config import get_settings
from app.core.database import SessionLocal
from app.integrations.email import send_email


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email-to", help="Send a single SMTP test message to this controlled inbox")
    args = parser.parse_args()
    settings = get_settings()
    result = {
        "job": "billing_readiness_check",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "database": "not_checked",
        "smtp_configured": bool(settings.smtp_host),
        "smtp_test": "not_requested",
        "paystack_secret_configured": bool(settings.paystack_secret_key),
        "authorization_encryption_key_configured": bool(settings.billing_authorization_encryption_key),
        "automatic_renewals_enabled": settings.billing_renewals_enabled,
        "billing_notifications_enabled": settings.billing_renewal_notifications_enabled,
    }
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        result["database"] = "connected"
    except Exception as exc:
        result["database"] = f"error:{type(exc).__name__}"

    if args.email_to:
        if not settings.smtp_host:
            result["smtp_test"] = "not_sent_smtp_not_configured"
        else:
            sent = send_email(
                settings, args.email_to, "BizPilotPro SMTP readiness test",
                "This is a one-time test message requested by an administrator to verify SMTP connectivity.",
                log_body=False,
            )
            result["smtp_test"] = "accepted_by_smtp" if sent else "delivery_failed"

    result["status"] = "ok" if result["database"] == "connected" and result["smtp_test"] not in {"delivery_failed", "not_sent_smtp_not_configured"} else "error"
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
