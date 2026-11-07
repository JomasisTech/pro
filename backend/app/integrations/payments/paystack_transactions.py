"""Server-side Paystack transaction verification helpers.

This module retrieves transaction details and compares them with the values
already stored by trusted server-side code. It never activates a subscription
or changes an organization's plan.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

PAYSTACK_API_BASE_URL = "https://api.paystack.co"


class PaystackVerificationError(RuntimeError):
    """Raised when Paystack cannot provide a trustworthy verification result."""


async def fetch_verified_transaction(
    *,
    reference: str,
    secret_key: str,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch transaction details directly from Paystack using a secret key.

    The caller must compare the returned transaction against its own pending
    transaction record before granting any value. A browser redirect or a
    successful API envelope alone is not sufficient to activate a plan.
    """
    cleaned_reference = reference.strip() if isinstance(reference, str) else ""
    if not cleaned_reference or len(cleaned_reference) > 100:
        raise ValueError("A valid transaction reference is required.")
    if not secret_key.strip():
        raise ValueError("Paystack secret key is not configured.")

    url = f"{PAYSTACK_API_BASE_URL}/transaction/verify/{quote(cleaned_reference, safe='')}"
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
    try:
        response = await active_client.get(
            url,
            headers={
                "Authorization": f"Bearer {secret_key.strip()}",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise PaystackVerificationError("Paystack returned an invalid response.") from exc
    except httpx.HTTPStatusError as exc:
        raise PaystackVerificationError(
            f"Paystack transaction verification failed with HTTP {exc.response.status_code}."
        ) from exc
    except httpx.RequestError as exc:
        raise PaystackVerificationError("Could not reach Paystack to verify the transaction.") from exc
    finally:
        if owns_client:
            await active_client.aclose()

    if not isinstance(payload, dict) or payload.get("status") is not True:
        raise PaystackVerificationError("Paystack did not confirm the verification request.")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise PaystackVerificationError("Paystack returned no transaction details.")
    return data


def transaction_matches_expected(
    transaction: dict[str, Any],
    *,
    reference: str,
    amount_minor: int,
    currency: str,
    customer_email: str | None = None,
) -> bool:
    """Check Paystack transaction data against a trusted pending transaction.

    Amount is expressed in the currency's minor unit (kobo for NGN). Email is
    checked when supplied by the server-side pending transaction record.
    """
    if not isinstance(transaction, dict):
        return False
    if not isinstance(amount_minor, int) or isinstance(amount_minor, bool) or amount_minor <= 0:
        return False
    if transaction.get("status") != "success":
        return False
    if transaction.get("reference") != reference:
        return False
    if transaction.get("amount") != amount_minor:
        return False
    if transaction.get("currency") != currency.upper():
        return False

    if customer_email is not None:
        customer = transaction.get("customer")
        actual_email = customer.get("email") if isinstance(customer, dict) else None
        if not isinstance(actual_email, str) or actual_email.casefold() != customer_email.casefold():
            return False
    return True
