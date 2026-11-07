import hashlib
import hmac

from app.integrations.payments.paystack import verify_webhook_signature


def _digest(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()


def test_verifies_modern_timestamped_webhook_signature() -> None:
    body = b'{"event":"charge.success","data":{"amount":250000}}'
    secret = "whsec_test_signing_secret"
    timestamp = 1_800_000_000
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha512).hexdigest()

    assert verify_webhook_signature(
        raw_body=body,
        paystack_signature=f"t={timestamp},v1=whk_test:{digest}",
        x_paystack_signature=None,
        webhook_secret=secret,
        secret_key="",
        now=timestamp,
    )


def test_modern_signature_accepts_any_valid_rotation_signature() -> None:
    body = b'{"event":"charge.success"}'
    secret = "new-webhook-secret"
    timestamp = 1_800_000_000
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha512).hexdigest()

    assert verify_webhook_signature(
        raw_body=body,
        paystack_signature=f"t={timestamp},v1=whk_old:{'a' * 128},v1=whk_new:{digest}",
        x_paystack_signature=None,
        webhook_secret=secret,
        secret_key="",
        now=timestamp,
    )


def test_rejects_timestamp_outside_five_minute_window() -> None:
    body = b'{"event":"charge.success"}'
    secret = "webhook-secret"
    timestamp = 1_800_000_000
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha512).hexdigest()

    assert not verify_webhook_signature(
        raw_body=body,
        paystack_signature=f"t={timestamp},v1=whk_test:{digest}",
        x_paystack_signature=None,
        webhook_secret=secret,
        secret_key="",
        now=timestamp + 301,
    )


def test_verifies_legacy_signature_using_secret_key() -> None:
    body = b'{"event":"charge.success"}'
    secret_key = "sk_test_example"

    assert verify_webhook_signature(
        raw_body=body,
        paystack_signature=None,
        x_paystack_signature=_digest(secret_key, body),
        webhook_secret="",
        secret_key=secret_key,
    )


def test_rejects_tampered_body_and_malformed_signatures() -> None:
    body = b'{"event":"charge.success"}'
    secret_key = "sk_test_example"

    assert not verify_webhook_signature(
        raw_body=body + b" ",
        paystack_signature=None,
        x_paystack_signature=_digest(secret_key, body),
        webhook_secret="",
        secret_key=secret_key,
    )
    assert not verify_webhook_signature(
        raw_body=body,
        paystack_signature="t=not-a-time,v1=whk_test:bad",
        x_paystack_signature="not-a-signature",
        webhook_secret="webhook-secret",
        secret_key=secret_key,
    )


def test_does_not_accept_a_signature_without_the_matching_secret() -> None:
    body = b'{"event":"charge.success"}'
    assert not verify_webhook_signature(
        raw_body=body,
        paystack_signature=None,
        x_paystack_signature=_digest("other-secret", body),
        webhook_secret="",
        secret_key="sk_test_example",
    )
