"""Boundary tests for the Firecrawl fetch provider.

These tests lock that Firecrawl provider import and construction are network-free.
Live Firecrawl execution belongs only inside FirecrawlFetchProvider.fetch().
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import Mock

import pytest
import requests


def test_importing_firecrawl_provider_is_network_free(monkeypatch) -> None:
    """Importing the Firecrawl provider module must not call network/API paths."""
    post = Mock(
        side_effect=AssertionError("requests.post() must not run during import")
    )
    get = Mock(
        side_effect=AssertionError("requests.get() must not run during import")
    )

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    sys.modules.pop("src.fetch.firecrawl_provider", None)

    module = importlib.import_module("src.fetch.firecrawl_provider")

    assert module is not None
    post.assert_not_called()
    get.assert_not_called()


def test_constructing_firecrawl_provider_is_network_free(monkeypatch) -> None:
    """Constructing FirecrawlFetchProvider must not call Firecrawl/network."""
    from src.fetch.firecrawl_provider import FirecrawlFetchProvider

    post = Mock(
        side_effect=AssertionError(
            "requests.post() must not run during construction"
        )
    )
    get = Mock(
        side_effect=AssertionError(
            "requests.get() must not run during construction"
        )
    )

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    provider = FirecrawlFetchProvider()

    assert provider is not None
    post.assert_not_called()
    get.assert_not_called()


def test_get_fetch_provider_firecrawl_is_network_free(monkeypatch) -> None:
    """Looking up Firecrawl through the registry is network-free."""
    from src.fetch import get_fetch_provider

    post = Mock(
        side_effect=AssertionError(
            "requests.post() must not run in provider factory"
        )
    )
    get = Mock(
        side_effect=AssertionError(
            "requests.get() must not run in provider factory"
        )
    )

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    provider = get_fetch_provider("firecrawl")

    assert provider is not None
    assert provider.name == "firecrawl"
    post.assert_not_called()
    get.assert_not_called()


def test_firecrawl_fetch_missing_api_key_returns_failure_without_network(
    monkeypatch,
) -> None:
    """Missing FIRECRAWL_API_KEY should return FetchResult(ok=False) without network."""
    from src.fetch.firecrawl_provider import FirecrawlFetchProvider

    post = Mock(
        side_effect=AssertionError(
            "requests.post() must not run without API key"
        )
    )
    get = Mock(
        side_effect=AssertionError(
            "requests.get() must not run without API key"
        )
    )

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    provider = FirecrawlFetchProvider()
    result = provider.fetch("https://example.com")

    assert result.ok is False
    assert "api key" in result.error.lower()
    post.assert_not_called()
    get.assert_not_called()


def test_constructing_firecrawl_provider_with_api_key_is_network_free(
    monkeypatch,
) -> None:
    """Even with an API key, construction must not call network."""
    from src.fetch.firecrawl_provider import FirecrawlFetchProvider

    post = Mock(
        side_effect=AssertionError(
            "requests.post() must not run during construction"
        )
    )
    get = Mock(
        side_effect=AssertionError(
            "requests.get() must not run during construction"
        )
    )

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key-not-real")

    provider = FirecrawlFetchProvider()

    assert provider is not None
    post.assert_not_called()
    get.assert_not_called()
