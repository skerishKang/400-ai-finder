"""Focused contract tests for the opt-in legacy transport of RequestsFetchProvider.

Issue #945 (refactor stage): ``legacy_transport=True`` is an opt-in refinement of
the existing ``compatibility_mode=True`` path used only for crawler/mapper
migration. It must NOT change the default provider path and must NOT change the
previously-released ``compatibility_mode`` behavior (incl. the split
``(connect, read)`` timeout tuple).

All HTTP is blocked by monkeypatching ``requests.get`` (imported in the provider
as ``req_lib``). No real network, provider, API, LLM, or Firecrawl call occurs.

no network / legacy transport / scalar timeout / compatibility mode
"""

from __future__ import annotations

import pytest

from src.fetch.requests_provider import RequestsFetchProvider, req_lib
from src.fetch.base import FetchConfig


class FakeResponse:
    """Stand-in for a ``requests`` Response whose ``.text`` re-decodes on demand."""

    def __init__(
        self,
        *,
        status_code=200,
        url="https://example.test/final",
        content_type="text/html; charset=utf-8",
        content=b"",
        encoding="utf-8",
        apparent_encoding="utf-8",
    ):
        self.status_code = status_code
        self.url = url
        self.headers = {"Content-Type": content_type}
        self._content = content
        self.encoding = encoding
        self.apparent_encoding = apparent_encoding

    @property
    def text(self):
        enc = self.encoding or "utf-8"
        try:
            return self._content.decode(enc)
        except Exception:
            return self._content.decode(enc, errors="replace")


# ---------------------------------------------------------------------------
# 1. scalar timeout + verbatim headers
# ---------------------------------------------------------------------------
def test_legacy_transport_scalar_timeout_and_verbatim_headers(monkeypatch):
    """legacy transport / scalar timeout / compatibility mode / no network.

    With legacy_transport=True the caller's scalar timeout is forwarded verbatim
    (no split tuple) and the caller's headers are passed exactly as given.
    """
    captured = {}

    def mock_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(req_lib, "get", mock_get)

    provider = RequestsFetchProvider(timeout=15)
    headers = {"User-Agent": "LegacyContractUA"}
    result = provider.fetch(
        "https://example.test/start",
        compatibility_mode=True,
        legacy_transport=True,
        timeout=7,
        headers=headers,
    )

    # Exactly one request, scalar timeout preserved (not a tuple).
    assert "timeout" in captured
    assert captured["timeout"] == 7
    assert not isinstance(captured["timeout"], tuple)
    # Headers forwarded verbatim — identical dict, no merge with provider defaults.
    assert captured["headers"] == headers
    assert result.ok is True


# ---------------------------------------------------------------------------
# 2. 404 payload preservation (no retry despite FetchConfig retry settings)
# ---------------------------------------------------------------------------
def test_legacy_transport_404_preserves_payload(monkeypatch):
    """legacy transport / compatibility mode / no network.

    A 404 returns ok=False / "HTTP 404" while preserving final URL, status,
    content type, raw html and raw text. Even with a FetchConfig that would
    retry on 404, exactly ONE GET happens — no retry, no sleep. The ISO-8859-1
    body is normalized to its apparent encoding before being returned.
    """
    calls = []

    # Latin-1 bytes that decode differently under UTF-8 (c3 a9 -> é).
    iso_body = b"\xc3\xa9 <html>not found</html>"
    response = FakeResponse(
        status_code=404,
        url="https://example.test/notfound",
        content_type="text/html; charset=iso-8859-1",
        content=iso_body,
        encoding="ISO-8859-1",
        apparent_encoding="utf-8",
    )

    def mock_get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        return response

    monkeypatch.setattr(req_lib, "get", mock_get)

    provider = RequestsFetchProvider(timeout=15)
    config = FetchConfig(max_retries=3, retry_on_status=(404,), retry_backoff=1.0)

    result = provider.fetch(
        "https://example.test/notfound",
        config=config,
        compatibility_mode=True,
        legacy_transport=True,
        timeout=7,
        headers={"User-Agent": "LegacyContractUA"},
    )

    # Single request — retry config is ignored on the legacy transport path.
    assert len(calls) == 1
    assert result.ok is False
    assert result.error == "HTTP 404"
    assert result.status_code == 404
    assert result.url == "https://example.test/notfound"
    assert result.content_type == "text/html; charset=iso-8859-1"
    # Body preserved AND re-decoded under apparent (utf-8) encoding.
    assert "é" in result.html
    assert "é" in result.text
    assert result.html == result.text


# ---------------------------------------------------------------------------
# 3. timeout diagnostic shape (scalar timeout)
# ---------------------------------------------------------------------------
def test_legacy_transport_timeout_diagnostic(monkeypatch):
    """legacy transport / scalar timeout / compatibility mode / no network.

    A request timeout yields the scalar-timeout diagnostic form
    "Request timed out after <scalar>s" (no tuple formatting).
    """
    import requests

    def mock_get(url, headers=None, timeout=None):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(req_lib, "get", mock_get)

    provider = RequestsFetchProvider(timeout=15)
    result = provider.fetch(
        "https://example.test/slow",
        compatibility_mode=True,
        legacy_transport=True,
        timeout=7,
        headers={"User-Agent": "LegacyContractUA"},
    )

    assert result.ok is False
    assert result.error == "Request timed out after 7s"


# ---------------------------------------------------------------------------
# 4. regression: existing compatibility mode unchanged
# ---------------------------------------------------------------------------
def test_compatibility_mode_unchanged_without_legacy_transport(monkeypatch):
    """compatibility mode / no network.

    Without legacy_transport the existing compatibility path must still use the
    split (connect, read) timeout tuple. This guards against regressing the
    already-released behavior when legacy_transport is added.
    """
    captured = {}

    def mock_get(url, headers=None, timeout=None):
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(req_lib, "get", mock_get)

    provider = RequestsFetchProvider(timeout=15)
    provider.fetch(
        "https://example.test/start",
        compatibility_mode=True,
        timeout=7,
    )

    # Existing split timeout behavior is preserved: (connect=5.0, read=7.0).
    assert captured["timeout"] == (5.0, 7.0)
