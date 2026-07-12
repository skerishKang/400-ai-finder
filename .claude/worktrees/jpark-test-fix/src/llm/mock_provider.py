"""Mock provider for testing without real API calls."""

from __future__ import annotations

import os

from .base import LLMProvider, ProviderResult


MOCK_RESPONSE_ENV = "AI_FINDER_MOCK_RESPONSE"

_DEFAULT_MOCK_RESPONSE = (
    "## 답변\n\n"
    "검색 결과에 따르면 관련 정보를 찾았습니다.\n\n"
    "## 관련 자료\n\n"
    "- 예시 자료: https://example.com\n\n"
    "## 다음에 할 일\n\n"
    "1. 관련 페이지를 확인합니다.\n"
    "2. 필요한 서류를 준비합니다.\n\n"
    "## 확인 필요 사항\n\n"
    "실제 내용은 원문 확인이 필요합니다."
)


class MockProvider(LLMProvider):
    """Mock provider that returns a fixed response without API calls.

    The response can be customized via the AI_FINDER_MOCK_RESPONSE env var.
    """

    def __init__(self, response: str | None = None):
        self._response = response or os.environ.get(
            MOCK_RESPONSE_ENV, _DEFAULT_MOCK_RESPONSE
        )

    def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout: int = 60,
    ) -> ProviderResult:
        """Return the configured mock response."""
        return ProviderResult(
            ok=True,
            provider=self.provider_name,
            model=self.model_name,
            content=self._response,
            raw={
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock"
