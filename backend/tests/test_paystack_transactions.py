from __future__ import annotations

import httpx
import pytest

from app.integrations.payments.paystack_transactions import (
    PaystackVerificationError,
    fetch_verified_transaction,
    transaction_matches_expected,
)


@pytest.mark.asyncio
async def test_fetches_transaction_from_paystack_using_server_secret() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={"status": True, "data": {"reference": "ref-123", "status": "success"}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        data = await fetch_verified_transaction(reference="ref-123", secret_key="sk_test_secret", client=client)

    assert data == {"reference": "ref-123", "status": "success"}
    assert seen["url"] == "https://api.paystack.co/transaction/verify/ref-123"
    assert seen["authorization"] == "Bearer sk_test_secret"


@pytest.mark.asyncio
async def test_reference_is_url_encoded() -> None:
    seen_url = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_url
        seen_url = str(request.url)
        return httpx.Response(200, json={"status": True, "data": {"reference": "ref/123"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await fetch_verified_transaction(reference="ref/123", secret_key="sk_test", client=client)

    assert seen_url.endswith("/verify/ref%2F123")


@pytest.mark.asyncio
async def test_rejects_unsuccessful_api_envelope_and_invalid_data() -> None:
    responses = [
        httpx.Response(200, json={"status": False, "message": "not found"}),
        httpx.Response(200, json={"status": True, "data": []}),
        httpx.Response(200, content=b"not-json"),
    ]
    for response in responses:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _request, r=response: r)) as client:
            with pytest.raises(PaystackVerificationError):
                await fetch_verified_transaction(reference="ref-123", secret_key="sk_test", client=client)


@pytest.mark.asyncio
async def test_rejects_provider_http_error_and_network_error() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(401, json={"message": "unauthorized"}))
    ) as client:
        with pytest.raises(PaystackVerificationError, match="HTTP 401"):
            await fetch_verified_transaction(reference="ref-123", secret_key="sk_test", client=client)

    async def failing_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    async with httpx.AsyncClient(transport=httpx.MockTransport(failing_handler)) as client:
        with pytest.raises(PaystackVerificationError, match="Could not reach Paystack"):
            await fetch_verified_transaction(reference="ref-123", secret_key="sk_test", client=client)


@pytest.mark.asyncio
async def test_rejects_missing_reference_or_secret_before_network_call() -> None:
    with pytest.raises(ValueError):
        await fetch_verified_transaction(reference="  ", secret_key="sk_test")
    with pytest.raises(ValueError):
        await fetch_verified_transaction(reference="ref-123", secret_key=" ")


def _transaction() -> dict:
    return {
        "status": "success",
        "reference": "ref-123",
        "amount": 250000,
        "currency": "NGN",
        "customer": {"email": "owner@example.com"},
    }


def test_matches_successful_transaction_against_expected_values() -> None:
    assert transaction_matches_expected(
        _transaction(),
        reference="ref-123",
        amount_minor=250000,
        currency="ngn",
        customer_email="OWNER@example.com",
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "pending"},
        {"reference": "another-reference"},
        {"amount": 249999},
        {"currency": "USD"},
        {"customer": {"email": "attacker@example.com"}},
    ],
)
def test_rejects_transaction_mismatch(changes: dict) -> None:
    transaction = _transaction()
    transaction.update(changes)
    assert not transaction_matches_expected(
        transaction,
        reference="ref-123",
        amount_minor=250000,
        currency="NGN",
        customer_email="owner@example.com",
    )


def test_rejects_invalid_expected_amount_and_missing_customer() -> None:
    transaction = _transaction()
    assert not transaction_matches_expected(
        transaction, reference="ref-123", amount_minor=0, currency="NGN"
    )
    assert not transaction_matches_expected(
        transaction, reference="ref-123", amount_minor=250000, currency="NGN", customer_email=""
    )
