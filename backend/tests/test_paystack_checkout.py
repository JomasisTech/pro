import httpx
import pytest

from app.integrations.payments.base import CheckoutRequest
from app.integrations.payments.paystack_checkout import PaystackCheckoutError, PaystackProvider
from app.integrations.payments.registry import PaymentProviderUnavailable, get_payment_provider


@pytest.mark.anyio
async def test_paystack_checkout_initialization_uses_server_supplied_amount_and_currency():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = __import__("json").loads(request.content)
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"status": True, "data": {
            "authorization_url": "https://checkout.paystack.com/abc",
            "access_code": "access-123", "reference": "bp-ref-123",
        }})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PaystackProvider("sk_test_secret", client=client)
        result = await provider.initialize_checkout(CheckoutRequest(
            reference="bp-ref-123", email="customer@example.com", amount_minor=750000,
            currency="NGN", callback_url="https://app.example.com/billing/return",
            metadata={"plan_id": "standard"},
        ))

    assert result.authorization_url == "https://checkout.paystack.com/abc"
    assert result.access_code == "access-123"
    assert captured["authorization"] == "Bearer sk_test_secret"
    assert captured["payload"]["amount"] == 750000
    assert captured["payload"]["currency"] == "NGN"


@pytest.mark.anyio
async def test_paystack_checkout_rejects_mismatched_reference():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={
        "status": True, "data": {"authorization_url": "https://checkout.paystack.com/x", "reference": "other"}
    }))) as client:
        provider = PaystackProvider("sk_test_secret", client=client)
        with pytest.raises(PaystackCheckoutError):
            await provider.initialize_checkout(CheckoutRequest(
                reference="expected", email="a@example.com", amount_minor=999, currency="USD",
                callback_url="https://app.example.com/return", metadata={},
            ))


def test_provider_registry_keeps_future_processors_inactive():
    with pytest.raises(PaymentProviderUnavailable, match="future provider"):
        get_payment_provider("paypal")
    with pytest.raises(PaymentProviderUnavailable, match="future provider"):
        get_payment_provider("flutterwave")
    with pytest.raises(PaymentProviderUnavailable, match="not configured"):
        get_payment_provider("paystack", settings=type("Settings", (), {"paystack_secret_key": "", "paystack_webhook_secret": ""})())


@pytest.mark.anyio
async def test_paystack_recurring_charge_uses_server_amount_reference_and_authorization():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = __import__("json").loads(request.content)
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"status": True, "data": {
            "status": "success", "reference": "bp-renewal-123", "amount": 750000,
            "currency": "NGN", "authorization": {"reusable": True},
        }})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PaystackProvider("sk_test_secret", client=client)
        result = await provider.charge_authorization(
            authorization_code="AUTH_test123", email="billing@example.com",
            amount_minor=750000, currency="NGN", reference="bp-renewal-123",
            metadata={"subscription_id": "sub-1"}, callback_url="https://app.example.com/billing?renewal_reference=bp-renewal-123",
        )

    assert captured["url"].endswith("/transaction/charge_authorization")
    assert captured["authorization"] == "Bearer sk_test_secret"
    assert captured["payload"]["authorization_code"] == "AUTH_test123"
    assert captured["payload"]["amount"] == 750000
    assert captured["payload"]["reference"] == "bp-renewal-123"
    assert captured["payload"]["callback_url"] == "https://app.example.com/billing?renewal_reference=bp-renewal-123"
    assert result["status"] == "success"


@pytest.mark.anyio
async def test_paystack_recurring_charge_rejects_invalid_reference_and_currency():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))) as client:
        provider = PaystackProvider("sk_test_secret", client=client)
        with pytest.raises(ValueError, match="Unsupported recurring charge currency"):
            await provider.charge_authorization(
                authorization_code="AUTH_test123", email="a@example.com", amount_minor=100,
                currency="EUR", reference="bp-renewal-123",
            )
        with pytest.raises(ValueError, match="Invalid recurring charge reference"):
            await provider.charge_authorization(
                authorization_code="AUTH_test123", email="a@example.com", amount_minor=100,
                currency="NGN", reference="invalid reference",
            )


@pytest.mark.anyio
async def test_paystack_deactivates_authorization_with_secret_key():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = __import__("json").loads(request.content)
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"status": True, "message": "Authorization has been deactivated"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PaystackProvider("sk_test_secret", client=client)
        result = await provider.deactivate_authorization(authorization_code="AUTH_revoke_test")

    assert captured["url"].endswith("/customer/authorization/deactivate")
    assert captured["authorization"] == "Bearer sk_test_secret"
    assert captured["payload"] == {"authorization_code": "AUTH_revoke_test"}
    assert result["status"] is True


@pytest.mark.anyio
async def test_paystack_deactivation_rejects_invalid_authorization_code():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))) as client:
        provider = PaystackProvider("sk_test_secret", client=client)
        with pytest.raises(ValueError, match="valid Paystack authorization"):
            await provider.deactivate_authorization(authorization_code="bad-code")


@pytest.mark.anyio
async def test_paystack_regulator_wait_is_exposed_as_explicit_retry_window():
    from app.integrations.payments.paystack_checkout import PaystackRetryWindowError

    def handler(_request):
        return httpx.Response(400, json={
            "status": False,
            "message": "Charge attempt cannot be fulfilled until 20 minutes",
            "data": {"retry_by": "not-a-timestamp"},
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PaystackProvider("sk_test_secret", client=client)
        with pytest.raises(PaystackRetryWindowError) as exc:
            await provider.charge_authorization(
                authorization_code="AUTH_test123", email="billing@example.com",
                amount_minor=750000, currency="NGN", reference="bp-renewal-retry-1",
            )
    assert exc.value.retry_at > __import__("datetime").datetime.now(__import__("datetime").timezone.utc)


@pytest.mark.anyio
async def test_generic_paystack_charge_error_does_not_authorize_automatic_retry():
    from app.integrations.payments.paystack_checkout import PaystackRetryWindowError

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(400, json={
        "status": False, "message": "Insufficient funds", "data": {},
    }))) as client:
        provider = PaystackProvider("sk_test_secret", client=client)
        with pytest.raises(PaystackCheckoutError) as exc:
            await provider.charge_authorization(
                authorization_code="AUTH_test123", email="billing@example.com",
                amount_minor=750000, currency="NGN", reference="bp-renewal-retry-2",
            )
    assert not isinstance(exc.value, PaystackRetryWindowError)
