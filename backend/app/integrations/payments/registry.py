"""Central payment-provider factory. Add a new adapter here without changing billing routes."""
from app.config import Settings, get_settings
from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.paystack_checkout import PaystackProvider


class PaymentProviderUnavailable(RuntimeError):
    """Requested payment provider is not implemented or not configured."""


def get_payment_provider(provider_id: str, settings: Settings | None = None) -> PaymentProvider:
    config = settings or get_settings()
    if provider_id == "paystack":
        if not config.paystack_secret_key:
            raise PaymentProviderUnavailable("Paystack is not configured.")
        return PaystackProvider(config.paystack_secret_key, config.paystack_webhook_secret)
    if provider_id in {"paypal", "flutterwave"}:
        raise PaymentProviderUnavailable(f"{provider_id.title()} is registered as a future provider, not yet implemented.")
    raise PaymentProviderUnavailable("Unknown payment provider.")
