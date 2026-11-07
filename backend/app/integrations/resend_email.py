"""Resend HTTP API adapter for campaign email delivery (stdlib only)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailSendResult:
    accepted: bool
    provider_message_id: str | None = None
    retryable: bool = True
    error: str | None = None


def send_campaign_email(settings: Settings, *, to_address: str, subject: str, body: str, idempotency_key: str) -> EmailSendResult:
    """Submit one campaign email; same idempotency key makes retries safe at Resend."""
    if not settings.resend_api_key:
        return EmailSendResult(False, retryable=False, error="Resend API key is not configured")
    payload = json.dumps({
        "from": settings.email_from,
        "to": [to_address],
        "subject": subject,
        "text": body,
    }).encode("utf-8")
    request = Request(
        "https://api.resend.com/emails", data=payload, method="POST",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key[:256],
        },
    )
    try:
        with urlopen(request, timeout=settings.email_provider_timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
        message_id = result.get("id") if isinstance(result, dict) else None
        if not message_id:
            return EmailSendResult(False, retryable=True, error="Resend response did not include an email ID")
        return EmailSendResult(True, provider_message_id=str(message_id), retryable=False)
    except HTTPError as exc:
        detail = "Resend rejected the email request"
        try:
            data = json.loads(exc.read().decode("utf-8"))
            if isinstance(data, dict):
                detail = str(data.get("message") or data.get("name") or detail)[:250]
        except Exception:
            pass
        # Invalid payload/auth/configuration errors are not transient; rate limits and server errors are.
        retryable = exc.code == 429 or exc.code >= 500 or exc.code in {408, 409}
        log.warning("Resend API returned HTTP %s", exc.code)
        return EmailSendResult(False, retryable=retryable, error=detail)
    except (URLError, TimeoutError, OSError, ValueError):
        log.exception("Resend email request failed")
        return EmailSendResult(False, retryable=True, error="Temporary email provider connection failure")
