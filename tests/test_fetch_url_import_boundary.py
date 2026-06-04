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


def test_fetch_url_list_providers_is_no_network(monkeypatch, capsys, cleanup_module) -> None:
    """Lock that fetch_url --list-providers is a no-network informational path."""
    import scripts.fetch_url as fetch_url

    requests_get = Mock(side_effect=AssertionError("requests.get called"))
    requests_fetch = Mock(
        side_effect=AssertionError("RequestsFetchProvider.fetch called")
    )
    firecrawl_fetch = Mock(
        side_effect=AssertionError("FirecrawlFetchProvider.fetch called")
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
    # --url is required by argparse but is never used when --list-providers exits early
    monkeypatch.setattr(
        "sys.argv",
        ["fetch_url.py", "--url", "https://example.com", "--list-providers"],
    )

    with pytest.raises(SystemExit) as exc_info:
        fetch_url.main()

    assert exc_info.value.code in (None, 0)

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "provider" in output.lower() or "requests" in output.lower() or "mock" in output.lower()

    requests_get.assert_not_called()
    requests_fetch.assert_not_called()
    firecrawl_fetch.assert_not_called()
