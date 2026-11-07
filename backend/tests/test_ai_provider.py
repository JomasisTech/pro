import httpx
import pytest

from app.integrations.ai_provider import AIProviderError, OpenAIProvider, build_ai_provider


def provider_with(handler) -> OpenAIProvider:
    return OpenAIProvider("sk-test-secret", "test-model", transport=httpx.MockTransport(handler))


def test_successful_response_is_parsed_and_request_is_well_formed() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "  Hello world  "}}]})

    result = provider_with(handler).generate_text("system text", "user text")
    assert result.text == "Hello world"
    assert result.model == "test-model"
    assert seen["auth"] == "Bearer sk-test-secret"
    assert seen["url"].endswith("/chat/completions")
    assert "system text" in seen["body"] and "user text" in seen["body"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={"error": "bad key"}),
        httpx.Response(500, text="boom"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]}),
    ],
)
def test_bad_provider_responses_raise_without_leaking_the_key(response: httpx.Response) -> None:
    with pytest.raises(AIProviderError) as error:
        provider_with(lambda request: response).generate_text("s", "u")
    assert "sk-test-secret" not in str(error.value)


def test_network_failure_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(AIProviderError):
        provider_with(handler).generate_text("s", "u")


def test_no_provider_is_built_without_an_api_key() -> None:
    assert build_ai_provider("", "m", 5) is None
    assert build_ai_provider("   ", "m", 5) is None
    assert build_ai_provider("sk-x", "m", 5) is not None
