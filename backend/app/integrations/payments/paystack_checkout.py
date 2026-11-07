"""Paystack Checkout adapter. Google Pay is surfaced by Paystack Checkout when enabled."""
from __future__ import annotations

from typing import Any
from datetime import datetime, timedelta, timezone
import re
import httpx

from app.integrations.payments.base import CheckoutRequest, CheckoutSession
from app.integrations.payments.paystack import verify_webhook_signature
from app.integrations.payments.paystack_transactions import fetch_verified_transaction

PAYSTACK_API_BASE_URL = "https://api.paystack.co"


class PaystackCheckoutError(RuntimeError):
    """Paystack did not return a usable hosted checkout session."""


class PaystackRetryWindowError(PaystackCheckoutError):
    """Paystack explicitly supplied a safe future retry window for a charge."""

    def __init__(self, message: str, retry_at: datetime):
        super().__init__(message)
        self.retry_at = retry_at


def _provider_retry_window(envelope: Any) -> datetime | None:
    """Accept only Paystack's explicit regulator delay; never infer from generic failures."""
    if not isinstance(envelope, dict):
        return None
    data = envelope.get("data")
    message = str(envelope.get("message") or "").lower()
    if not isinstance(data, dict):
        return None
    retry_by = data.get("retry_by")
    if isinstance(retry_by, str):
        try:
            parsed = datetime.fromisoformat(retry_by.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    # Paystack's regulator error may include an explicit wait in minutes.
    match = re.search(r"charge attempt cannot be fulfilled until\s+(\d+)\s+minutes?", message)
    if match:
        minutes = int(match.group(1))
        if 1 <= minutes <= 1440:
            return datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return None


class PaystackProvider:
    provider_id = "paystack"

    def __init__(self, secret_key: str, webhook_secret: str = "", *, client: httpx.AsyncClient | None = None) -> None:
        self.secret_key = secret_key.strip()
        self.webhook_secret = webhook_secret.strip()
        self.client = client

    async def verify_transaction(self, reference: str) -> dict[str, Any]:
        return await fetch_verified_transaction(reference=reference, secret_key=self.secret_key, client=self.client)

    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        normalized = {key.casefold(): value for key, value in headers.items()}
        return verify_webhook_signature(
            raw_body=raw_body, paystack_signature=normalized.get("paystack-signature"),
            x_paystack_signature=normalized.get("x-paystack-signature"),
            webhook_secret=self.webhook_secret, secret_key=self.secret_key,
        )

    async def charge_authorization(
        self, *, authorization_code: str, email: str, amount_minor: int,
        currency: str, reference: str, metadata: dict[str, Any] | None = None,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        """Request a recurring debit against a Paystack authorization.

        This primitive does not activate subscriptions. Callers must verify the
        returned reference server-to-server before fulfilling a billing period.
        The authorization must have been explicitly consented to and marked
        reusable by Paystack before it is stored/used.
        """
        if not self.secret_key:
            raise PaystackCheckoutError("Paystack secret key is not configured.")
        if not authorization_code.startswith("AUTH_") or not email or amount_minor <= 0:
            raise ValueError("A valid reusable authorization, customer email and positive amount are required.")
        if currency not in {"NGN", "USD"}:
            raise ValueError("Unsupported recurring charge currency.")
        if not reference or len(reference) > 120 or not all(ch.isalnum() or ch in "-.=" for ch in reference):
            raise ValueError("Invalid recurring charge reference.")
        payload = {
            "authorization_code": authorization_code, "email": email,
            "amount": amount_minor, "currency": currency, "reference": reference,
            "metadata": metadata or {},
        }
        if callback_url:
            payload["callback_url"] = callback_url
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0))
        try:
            response = await client.post(
                f"{PAYSTACK_API_BASE_URL}/transaction/charge_authorization",
                json=payload,
                headers={"Authorization": f"Bearer {self.secret_key}", "Accept": "application/json"},
            )
            try:
                envelope: Any = response.json()
            except ValueError as exc:
                if response.is_error:
                    raise PaystackCheckoutError(f"Paystack recurring charge failed (HTTP {response.status_code}).") from exc
                raise PaystackCheckoutError("Paystack returned an invalid recurring-charge response.") from exc
            if response.is_error:
                retry_at = _provider_retry_window(envelope)
                message = str(envelope.get("message") or "Paystack recurring charge was rejected.") if isinstance(envelope, dict) else "Paystack recurring charge was rejected."
                if retry_at is not None:
                    raise PaystackRetryWindowError(message, retry_at)
                raise PaystackCheckoutError(f"Paystack recurring charge failed (HTTP {response.status_code}): {message}")
        except httpx.HTTPStatusError as exc:
            raise PaystackCheckoutError(f"Paystack recurring charge failed (HTTP {exc.response.status_code}).") from exc
        except httpx.RequestError as exc:
            raise PaystackCheckoutError("Could not reach Paystack to initiate the recurring charge.") from exc
        finally:
            if owns_client:
                await client.aclose()

        data = envelope.get("data") if isinstance(envelope, dict) and envelope.get("status") is True else None
        if not isinstance(data, dict):
            retry_at = _provider_retry_window(envelope)
            message = envelope.get("message") if isinstance(envelope, dict) else None
            if retry_at is not None:
                raise PaystackRetryWindowError(str(message or "Paystack requested a delayed retry."), retry_at)
            raise PaystackCheckoutError(str(message or "Paystack did not accept the recurring charge."))
        returned_reference = data.get("reference")
        if returned_reference != reference:
            raise PaystackCheckoutError("Paystack returned a mismatched recurring-charge reference.")
        return data

    async def deactivate_authorization(self, *, authorization_code: str) -> dict[str, Any]:
        """Deactivate a reusable authorization at Paystack when the customer withdraws consent."""
        if not self.secret_key:
            raise PaystackCheckoutError("Paystack secret key is not configured.")
        if not isinstance(authorization_code, str) or not authorization_code.startswith("AUTH_"):
            raise ValueError("A valid Paystack authorization code is required.")
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0))
        try:
            response = await client.post(
                f"{PAYSTACK_API_BASE_URL}/customer/authorization/deactivate",
                json={"authorization_code": authorization_code},
                headers={"Authorization": f"Bearer {self.secret_key}", "Accept": "application/json"},
            )
            response.raise_for_status()
            try:
                envelope: Any = response.json()
            except ValueError as exc:
                raise PaystackCheckoutError("Paystack returned an invalid authorization-deactivation response.") from exc
        except httpx.HTTPStatusError as exc:
            raise PaystackCheckoutError(f"Paystack authorization deactivation failed (HTTP {exc.response.status_code}).") from exc
        except httpx.RequestError as exc:
            raise PaystackCheckoutError("Could not reach Paystack to deactivate the saved authorization.") from exc
        finally:
            if owns_client:
                await client.aclose()
        if not isinstance(envelope, dict) or envelope.get("status") is not True:
            message = envelope.get("message") if isinstance(envelope, dict) else None
            raise PaystackCheckoutError(str(message or "Paystack did not confirm authorization deactivation."))
        return envelope

    async def initialize_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        if not self.secret_key:
            raise PaystackCheckoutError("Paystack secret key is not configured.")
        if request.amount_minor <= 0 or request.currency not in {"NGN", "USD"}:
            raise ValueError("Unsupported checkout amount or currency.")
        payload = {
            "email": request.email,
            "amount": request.amount_minor,
            "currency": request.currency,
            "reference": request.reference,
            "callback_url": request.callback_url,
            "metadata": request.metadata,
        }
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=5.0))
        try:
            response = await client.post(
                f"{PAYSTACK_API_BASE_URL}/transaction/initialize",
                json=payload,
                headers={"Authorization": f"Bearer {self.secret_key}", "Accept": "application/json"},
            )
            response.raise_for_status()
            try:
                envelope: Any = response.json()
            except ValueError as exc:
                raise PaystackCheckoutError("Paystack returned an invalid response.") from exc
        except httpx.HTTPStatusError as exc:
            raise PaystackCheckoutError(f"Paystack checkout initialization failed (HTTP {exc.response.status_code}).") from exc
        except httpx.RequestError as exc:
            raise PaystackCheckoutError("Could not reach Paystack to initialize checkout.") from exc
        finally:
            if owns_client:
                await client.aclose()

        data = envelope.get("data") if isinstance(envelope, dict) and envelope.get("status") is True else None
        if not isinstance(data, dict):
            raise PaystackCheckoutError("Paystack did not return a checkout session.")
        authorization_url = data.get("authorization_url")
        access_code = data.get("access_code")
        returned_reference = data.get("reference")
        if not isinstance(authorization_url, str) or not authorization_url.startswith("https://"):
            raise PaystackCheckoutError("Paystack returned an invalid checkout URL.")
        if returned_reference != request.reference:
            raise PaystackCheckoutError("Paystack returned a mismatched transaction reference.")
        return CheckoutSession(authorization_url, access_code if isinstance(access_code, str) else None, returned_reference)
