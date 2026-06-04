"""Import boundary tests for scripts.diagnose_site.

These tests lock that importing the CLI module is network-free and does not
execute diagnostics. Live execution belongs behind explicit CLI invocation only.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import Mock

import pytest
import requests

from src.fetch.firecrawl_provider import FirecrawlFetchProvider
from src.fetch.requests_provider import RequestsFetchProvider


def test_importing_diagnose_site_is_network_free(monkeypatch) -> None:
    """Importing scripts.diagnose_site must not execute fetch/network paths."""
    requests_get = Mock(
        side_effect=AssertionError("requests.get() must not run during import")
    )
    requests_fetch = Mock(
        side_effect=AssertionError(
            "RequestsFetchProvider.fetch() must not run during import"
        )
    )
    firecrawl_fetch = Mock(
        side_effect=AssertionError(
            "FirecrawlFetchProvider.fetch() must not run during import"
        )
    )

    monkeypatch.setattr(requests, "get", requests_get)
    monkeypatch.setattr(RequestsFetchProvider, "fetch", requests_fetch)
    monkeypatch.setattr(FirecrawlFetchProvider, "fetch", firecrawl_fetch)
    monkeypatch.delenv("AI_FINDER_FETCH_PROVIDER", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    sys.modules.pop("scripts.diagnose_site", None)

    module = importlib.import_module("scripts.diagnose_site")

    assert module is not None
    requests_get.assert_not_called()
    requests_fetch.assert_not_called()
    firecrawl_fetch.assert_not_called()
