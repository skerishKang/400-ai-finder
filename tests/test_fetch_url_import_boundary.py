import importlib
import sys
from unittest.mock import Mock

import pytest


@pytest.fixture
def cleanup_module():
    """Ensure scripts.fetch_url is removed from sys.modules after the test."""
    yield
    sys.modules.pop("scripts.fetch_url", None)


def test_fetch_url_import_is_network_free(monkeypatch, cleanup_module) -> None:
    """Lock that importing scripts.fetch_url performs no provider/fetch/network calls."""
    # Guard all possible network call paths at import time
    requests_get = Mock(
        side_effect=AssertionError("requests.get called during import")
    )
    requests_fetch = Mock(
        side_effect=AssertionError(
            "RequestsFetchProvider.fetch called during import"
        )
    )
    firecrawl_fetch = Mock(
        side_effect=AssertionError(
            "FirecrawlFetchProvider.fetch called during import"
        )
    )

    monkeypatch.setattr("requests.get", requests_get, raising=False)
    monkeypatch.setattr(
        "src.fetch.requests_provider.RequestsFetchProvider.fetch",
        requests_fetch,
        raising=False,
    )
    monkeypatch.setattr(
        "src.fetch.firecrawl_provider.FirecrawlFetchProvider.fetch",
        firecrawl_fetch,
        raising=False,
    )

    # Remove any cached import
    sys.modules.pop("scripts.fetch_url", None)

    module = importlib.import_module("scripts.fetch_url")

    assert module is not None
    requests_get.assert_not_called()
    requests_fetch.assert_not_called()
    firecrawl_fetch.assert_not_called()
