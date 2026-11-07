"""Provider-neutral contracts for future payment integrations."""
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CheckoutRequest:
    reference: str
    email: str
    amount_minor: int
    currency: str
    callback_url: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class CheckoutSession:
    authorization_url: str
    access_code: str | None
    reference: str


class PaymentProvider(Protocol):
    """A payment processor adapter; provider-specific details stay behind this contract."""

    provider_id: str

    async def initialize_checkout(self, request: CheckoutRequest) -> CheckoutSession: ...

    async def verify_transaction(self, reference: str) -> dict[str, Any]: ...

    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool: ...


PROVIDER_CATALOG = {
    "paystack": {"status": "initial", "implemented": True, "channels": ["card", "google_pay"]},
    "paypal": {"status": "future", "implemented": False, "channels": []},
    "flutterwave": {"status": "future", "implemented": False, "channels": []},
}
