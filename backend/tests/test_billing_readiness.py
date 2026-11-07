from fastapi.testclient import TestClient


def test_billing_catalog_does_not_claim_checkout_is_live(client: TestClient) -> None:
    response = client.get("/api/v1/billing/plans")
    assert response.status_code == 200
    payload = response.json()
    assert payload["prices_configured"] is False  # SQLite test fixture does not run the seed migration.
    assert payload["checkout_enabled"] is False
    assert {plan["id"] for plan in payload["plans"]} == {"free", "standard", "premium"}


def test_billing_readiness_is_explicit(client: TestClient) -> None:
    response = client.get("/api/v1/billing/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "paystack"
    assert payload["checkout_enabled"] is False
    assert payload["webhooks_enabled"] is False
