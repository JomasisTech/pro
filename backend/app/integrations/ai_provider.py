"""Reusable communication with AI providers.

Business code depends on the small `AIProvider` interface, not on OpenAI directly, so another provider
can be added later without touching content logic.
"""

from dataclasses import dataclass
from typing import Protocol

import httpx


class AIProviderError(Exception):
    """The provider failed or returned something unusable. The message is safe to log, never contains secrets."""


@dataclass(frozen=True)
class GeneratedText:
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    provider: str = "openai"


class AIProvider(Protocol):
    def generate_text(self, system_prompt: str, user_prompt: str) -> GeneratedText: ...


class OpenAIProvider:
    """Calls the OpenAI Chat Completions HTTP API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        base_url: str = "https://api.openai.com/v1",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    def generate_text(self, system_prompt: str, user_prompt: str) -> GeneratedText:
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
        except httpx.HTTPError as error:
            raise AIProviderError(f"Could not reach the AI provider ({type(error).__name__})") from None

        if response.status_code != 200:
            raise AIProviderError(f"The AI provider returned HTTP {response.status_code}")
        try:
            body = response.json()
            text = body["choices"][0]["message"]["content"]
            usage = body.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
        except (ValueError, KeyError, IndexError, TypeError):
            raise AIProviderError("The AI provider returned an unexpected response") from None
        if not isinstance(text, str) or not text.strip():
            raise AIProviderError("The AI provider returned an empty response")
        def safe_count(value):
            return value if isinstance(value, int) and value >= 0 else None
        return GeneratedText(text=text.strip(), model=self._model,
            prompt_tokens=safe_count(prompt_tokens), completion_tokens=safe_count(completion_tokens),
            total_tokens=safe_count(total_tokens), provider="openai")


def build_ai_provider(api_key: str, model: str, timeout_seconds: float) -> AIProvider | None:
    """Return a provider, or None when no API key is configured."""
    if not api_key.strip():
        return None
    return OpenAIProvider(api_key=api_key.strip(), model=model, timeout_seconds=timeout_seconds)
