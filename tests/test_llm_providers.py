"""Tests for LLM provider abstraction layer.

All tests use MockProvider or monkeypatched requests — no real API calls.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.llm import (
    LLMProvider,
    ProviderResult,
    MockProvider,
    OpenAICompatibleProvider,
    get_provider,
    list_providers,
    BUILTIN_PROVIDERS,
)


# ======================================================================
# MockProvider tests
# ======================================================================

class TestMockProvider:
    def test_default_response(self):
        """Mock provider returns the default response."""
        provider = MockProvider()
        result = provider.complete(messages=[{"role": "user", "content": "hi"}])
        assert result.ok is True
        assert result.provider == "mock"
        assert result.model == "mock"
        assert "답변" in result.content

    def test_custom_response(self):
        """Mock provider returns a custom response when configured."""
        custom = "Custom test response"
        provider = MockProvider(response=custom)
        result = provider.complete(messages=[])
        assert result.ok is True
        assert result.content == custom

    def test_env_response(self):
        """Mock provider reads from environment variable."""
        with patch.dict(os.environ, {"AI_FINDER_MOCK_RESPONSE": "env response"}):
            provider = MockProvider()
            result = provider.complete(messages=[])
            assert result.content == "env response"

    def test_messages_preserved_in_raw(self):
        """The messages list is preserved in raw output."""
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hello"}]
        provider = MockProvider()
        result = provider.complete(messages=messages, temperature=0.5, max_tokens=100)
        assert result.raw["messages"] == messages
        assert result.raw["temperature"] == 0.5
        assert result.raw["max_tokens"] == 100


# ======================================================================
# Provider factory tests
# ======================================================================

class TestGetProvider:
    def test_mock_provider(self):
        provider = get_provider("mock")
        assert isinstance(provider, MockProvider)

    def test_openai_compatible_provider(self):
        """openai_compatible returns an OpenAICompatibleProvider even without env vars."""
        provider = get_provider("openai_compatible")
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_builtin_providers(self):
        """All built-in providers resolve to OpenAICompatibleProvider."""
        for name in BUILTIN_PROVIDERS:
            provider = get_provider(name)
            assert isinstance(provider, OpenAICompatibleProvider), f"{name} failed"

    def test_unknown_provider_raises(self):
        """Unknown provider name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_provider("nonexistent_provider_xyz")

    def test_env_default(self):
        """get_provider(None) reads AI_FINDER_LLM_PROVIDER env var."""
        with patch.dict(os.environ, {"AI_FINDER_LLM_PROVIDER": "mock"}):
            provider = get_provider()
            assert isinstance(provider, MockProvider)

    def test_env_default_fallback(self):
        """get_provider(None) falls back to mock when env is not set."""
        with patch.dict(os.environ, {}, clear=True):
            provider = get_provider()
            assert isinstance(provider, MockProvider)


class TestListProviders:
    def test_returns_list(self):
        providers = list_providers()
        assert isinstance(providers, list)
        assert len(providers) > 1

    def test_mock_included(self):
        names = [p["name"] for p in list_providers()]
        assert "mock" in names

    def test_builtin_included(self):
        names = [p["name"] for p in list_providers()]
        for name in BUILTIN_PROVIDERS:
            assert name in names, f"{name} missing from list_providers()"


# ======================================================================
# OpenAICompatibleProvider tests
# ======================================================================

class TestOpenAICompatibleProviderConfigValidation:
    """Config validation errors return ProviderResult, not exceptions."""

    def test_missing_base_url(self):
        provider = OpenAICompatibleProvider(
            base_url="",
            api_key="test-key",
            model="test-model",
        )
        result = provider.complete(messages=[{"role": "user", "content": "hi"}])
        assert result.ok is False
        assert "base url" in result.error.lower()

    def test_missing_api_key(self):
        provider = OpenAICompatibleProvider(
            base_url="https://example.com/v1",
            api_key="",
            model="test-model",
        )
        result = provider.complete(messages=[{"role": "user", "content": "hi"}])
        assert result.ok is False
        assert "api key" in result.error.lower()

    def test_missing_model(self):
        provider = OpenAICompatibleProvider(
            base_url="https://example.com/v1",
            api_key="test-key",
            model="",
        )
        result = provider.complete(messages=[{"role": "user", "content": "hi"}])
        assert result.ok is False
        assert "model" in result.error.lower()

    def test_error_does_not_leak_api_key(self):
        """Error messages should not contain the actual API key value."""
        provider = OpenAICompatibleProvider(
            base_url="",
            api_key="super-secret-key-12345",
            model="test-model",
        )
        result = provider.complete(messages=[{"role": "user", "content": "hi"}])
        assert result.ok is False
        assert "super-secret-key-12345" not in result.error


class TestOpenAICompatibleProviderRequest:
    """Test that requests are built correctly using monkeypatch."""

    def test_endpoint_and_headers(self):
        """Verify the endpoint is /chat/completions and auth header is present."""
        captured = {}

        def fake_post(url, headers, json, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            captured["timeout"] = timeout

            class FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "choices": [{
                            "message": {"content": "Hello from fake API"}
                        }]
                    }

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = OpenAICompatibleProvider(
                base_url="https://api.test.com/v1",
                api_key="test-key-abc",
                model="gpt-4o-mini",
                timeout=30,
                temperature=0.3,
                max_tokens=500,
            )
            result = provider.complete(
                messages=[{"role": "user", "content": "hi"}],
            )

        # Endpoint check
        assert captured["url"] == "https://api.test.com/v1/chat/completions"

        # Auth header check (don't log the actual key)
        auth_header = captured["headers"].get("Authorization", "")
        assert auth_header.startswith("Bearer ")
        assert "test-key-abc" in auth_header  # check it's there, but don't log

        # Body check
        assert captured["json"]["model"] == "gpt-4o-mini"
        assert captured["json"]["messages"] == [{"role": "user", "content": "hi"}]
        assert captured["json"]["temperature"] == 0.3
        assert captured["json"]["max_tokens"] == 500

        # Result
        assert result.ok is True
        assert result.content == "Hello from fake API"


class TestOpenAICompatibleProviderResponseParsing:
    """Test response parsing edge cases."""

    def test_empty_choices(self):
        def fake_post(url, headers, json, timeout):
            class FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"choices": []}

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = OpenAICompatibleProvider(
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
            )
            result = provider.complete(messages=[{"role": "user", "content": "hi"}])
            assert result.ok is False
            assert "no choices" in result.error.lower()

    def test_empty_content(self):
        def fake_post(url, headers, json, timeout):
            class FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"choices": [{"message": {"content": ""}}]}

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = OpenAICompatibleProvider(
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
            )
            result = provider.complete(messages=[{"role": "user", "content": "hi"}])
            assert result.ok is False
            assert "empty content" in result.error.lower()

    def test_missing_message_key(self):
        def fake_post(url, headers, json, timeout):
            class FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"choices": [{"something_else": "value"}]}

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = OpenAICompatibleProvider(
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
            )
            result = provider.complete(messages=[{"role": "user", "content": "hi"}])
            assert result.ok is False
            # choices[0].message.content is empty when message key is missing
            assert result.error  # non-empty error message

    def test_http_error(self):
        def fake_post(url, headers, json, timeout):
            import requests

            class FakeResponse:
                status_code = 401
                text = "Unauthorized"

                def raise_for_status(self):
                    raise requests.exceptions.HTTPError(
                        "401 Client Error", response=self
                    )

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = OpenAICompatibleProvider(
                base_url="https://api.test.com/v1",
                api_key="bad-key",
                model="test-model",
            )
            result = provider.complete(messages=[{"role": "user", "content": "hi"}])
            assert result.ok is False
            assert "HTTP" in result.error
            assert "bad-key" not in result.error  # key not leaked

    def test_timeout(self):
        def fake_post(url, headers, json, timeout):
            import requests
            raise requests.exceptions.Timeout("Request timed out")

        with patch("requests.post", side_effect=fake_post):
            provider = OpenAICompatibleProvider(
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
                timeout=5,
            )
            result = provider.complete(messages=[{"role": "user", "content": "hi"}])
            assert result.ok is False
            assert "timed out" in result.error.lower()

    def test_json_decode_error(self):
        import json as json_module

        def fake_post(*args, **kwargs):
            class FakeResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    raise json_module.JSONDecodeError("Not JSON", doc="", pos=0)

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = OpenAICompatibleProvider(
                base_url="https://api.test.com/v1",
                api_key="test-key",
                model="test-model",
            )
            result = provider.complete(messages=[{"role": "user", "content": "hi"}])
            assert result.ok is False
            assert "invalid json" in result.error.lower()


# ======================================================================
# Live / Integration tests (Opt-in via API Key env vars)
# ======================================================================

class TestLiveLLMProviders:
    @pytest.mark.skipif(
        not os.environ.get("OPENGATEWAY_API_KEY"),
        reason="OPENGATEWAY_API_KEY env var not set (opt-in)",
    )
    def test_opengateway_live(self):
        """Test actual opengateway connection when API key is provided."""
        provider = get_provider("opengateway")
        messages = [{"role": "user", "content": "안녕하세요. 1+1은 뭐죠? 간단히 답해주세요."}]
        result = provider.complete(messages)
        assert result.ok is True
        assert result.provider == "opengateway"
        assert result.content

    @pytest.mark.skipif(
        not os.environ.get("KILOCODE_API_KEY"),
        reason="KILOCODE_API_KEY env var not set (opt-in)",
    )
    def test_kilocode_live(self):
        """Test actual kilocode connection when API key is provided."""
        provider = get_provider("kilocode")
        messages = [{"role": "user", "content": "안녕하세요. 1+1은 뭐죠? 간단히 답해주세요."}]
        result = provider.complete(messages)
        assert result.ok is True
        assert result.provider == "kilocode"
        assert result.content

    @pytest.mark.skipif(
        not os.environ.get("GROQ_API_KEY"),
        reason="GROQ_API_KEY env var not set (opt-in)",
    )
    def test_groq_live(self):
        """Test actual groq connection when API key is provided."""
        provider = get_provider("groq")
        messages = [{"role": "user", "content": "안녕하세요. 1+1은 뭐죠? 간단히 답해주세요."}]
        result = provider.complete(messages)
        assert result.ok is True
        assert result.provider == "groq"
        assert result.content
