"""Small, dependency-free Paystack webhook signature verification helpers.

This module deliberately verifies signatures only. It does not grant plans or
mark payments as successful; those actions require persisted transactions and
server-side transaction verification in a later billing increment.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time

_HEX_SHA512 = re.compile(r"^[0-9a-f]{128}$")
_DEFAULT_TIMESTAMP_TOLERANCE_SECONDS = 300


def verify_webhook_signature(
    *,
    raw_body: bytes,
    paystack_signature: str | None,
    x_paystack_signature: str | None,
    webhook_secret: str,
    secret_key: str,
    now: int | None = None,
    timestamp_tolerance_seconds: int = _DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
) -> bool:
    """Verify modern timestamped or legacy Paystack webhook signatures.

    Modern ``Paystack-Signature`` uses the webhook signing secret and signs
    ``timestamp + b'.' + raw_body``. Each v1 entry is ``key-id:hex-digest``.
    Legacy ``x-paystack-signature`` signs the raw body with the API secret key.
    The caller must pass the exact raw request bytes, not re-serialized JSON.
    """
    if not isinstance(raw_body, bytes):
        return False

    if paystack_signature and webhook_secret:
        if _verify_timestamped_signature(
            raw_body=raw_body,
            header=paystack_signature,
            secret=webhook_secret,
            now=int(time.time()) if now is None else now,
            tolerance=timestamp_tolerance_seconds,
        ):
            return True

    if x_paystack_signature and secret_key and _HEX_SHA512.fullmatch(x_paystack_signature):
        expected = hmac.new(secret_key.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(expected, x_paystack_signature)

    return False


def _verify_timestamped_signature(
    *, raw_body: bytes, header: str, secret: str, now: int, tolerance: int
) -> bool:
    timestamp: int | None = None
    signatures: list[str] = []

    for part in header.split(","):
        key, separator, value = part.strip().partition("=")
        if not separator:
            continue
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                return False
        elif key == "v1":
            _key_id, colon, digest = value.partition(":")
            if colon and _HEX_SHA512.fullmatch(digest):
                signatures.append(digest)

    if timestamp is None or not signatures or tolerance < 0:
        return False
    if abs(now - timestamp) > tolerance:
        return False

    signed_payload = str(timestamp).encode("ascii") + b"." + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha512).hexdigest()
    return any(hmac.compare_digest(expected, candidate) for candidate in signatures)
