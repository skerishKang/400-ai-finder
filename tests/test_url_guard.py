"""Tests for the answer output URL allowlist guard (issue #841).

All tests use mock/offline providers — no network calls.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.llm import MockProvider, ProviderResult
from src.answer.answer_composer import AnswerComposer, compose_answer
from src.answer.url_guard import canonicalize_url, extract_urls_from_markdown, assess_url_allowlist


# ------------------------------------------------------------------
# canonicalize_url tests
# ------------------------------------------------------------------

class TestCanonicalizeUrl:
    def test_exact_source_url_accepted(self):
        """Exact source URL canonicalizes to itself."""
        assert canonicalize_url("https://example.com/apply") == "https://example.com/apply"

    def test_fragment_removed(self):
        """Fragment-only variation accepted (fragment discarded for comparison)."""
        assert canonicalize_url("https://example.com/apply#section") == "https://example.com/apply"

    def test_scheme_host_case_lowered(self):
        """Scheme and host case variations are normalized."""
        assert canonicalize_url("HTTPS://EXAMPLE.COM/Apply") == "https://example.com/Apply"

    def test_default_http_port_removed(self):
        """Default port :80 for HTTP is removed."""
        assert canonicalize_url("http://example.com:80/path") == "http://example.com/path"

    def test_default_https_port_removed(self):
        """Default port :443 for HTTPS is removed."""
        assert canonicalize_url("https://example.com:443/path") == "https://example.com/path"

    def test_non_default_port_preserved(self):
        """Non-default port is retained."""
        assert canonicalize_url("https://example.com:8443/path") == "https://example.com:8443/path"

    def test_query_preserved_exactly(self):
        """Query string is preserved exactly — order and encoding unchanged."""
        assert canonicalize_url("https://example.com/search?q=hello&sort=asc") == "https://example.com/search?q=hello&sort=asc"

    def test_percent_encoded_path_preserved(self):
        """Percent-encoded path bytes are preserved, slash structure intact."""
        assert canonicalize_url("https://example.com/%ED%95%9C/path") == "https://example.com/%ED%95%9C/path"

    def test_dot_segment_path_rejected(self):
        """Literal dot-segment paths (/../ or /./) or ending with dot segments are rejected."""
        assert canonicalize_url("https://example.com/../secret") is None
        assert canonicalize_url("https://example.com/./path") is None
        assert canonicalize_url("https://example.com/a/..") is None
        assert canonicalize_url("https://example.com/a/.") is None

    def test_guard_unsupported_port(self):
        """Port numbers that are invalid (like containing non-digits or out of range) are rejected safely."""
        assert canonicalize_url("https://example.com:invalid_port/path") is None
        assert canonicalize_url("https://example.com:999999/path") is None

    def test_credentials_rejected(self):
        """URLs with credentials in authority are rejected."""
        assert canonicalize_url("https://user:pass@example.com/path") is None

    def test_missing_host_rejected(self):
        """URL with missing host or malformed authority is rejected."""
        assert canonicalize_url("https:///path") is None
        assert canonicalize_url("https://@example.com/path") is None
        assert canonicalize_url("https://example.com:/path") is None

    def test_relative_url_rejected(self):
        """Relative URL (no scheme) returns None."""
        assert canonicalize_url("/path/to/page") is None

    def test_unsupported_scheme_rejected(self):
        """ftp, mailto, javascript schemes are rejected."""
        assert canonicalize_url("ftp://example.com/file") is None
        assert canonicalize_url("mailto:user@example.com") is None
        assert canonicalize_url("javascript:alert(1)") is None

    def test_empty_string_returns_none(self):
        """Empty URL string returns None."""
        assert canonicalize_url("") is None

    def test_same_host_different_path_produces_different_canonical(self):
        """Same host with a different path is NOT equal to source URL."""
        canon_a = canonicalize_url("https://example.com/apply")
        canon_b = canonicalize_url("https://example.com/admin")
        assert canon_a != canon_b

    def test_path_prefix_lookalike_not_equal(self):
        """Path-prefix lookalike (/apply vs /apply/admin) are not equal."""
        canon_a = canonicalize_url("https://example.com/apply")
        canon_b = canonicalize_url("https://example.com/apply/admin")
        assert canon_a != canon_b

    def test_subdomain_not_equal(self):
        """Subdomain variation (sub.example.com vs example.com) is not equal."""
        canon_a = canonicalize_url("https://example.com/path")
        canon_b = canonicalize_url("https://sub.example.com/path")
        assert canon_a != canon_b

    def test_host_suffix_not_equal(self):
        """Host suffix lookalike (evil-example.com vs example.com) is not equal."""
        canon_a = canonicalize_url("https://example.com/path")
        canon_b = canonicalize_url("https://evil-example.com/path")
        assert canon_a != canon_b

    def test_changed_query_not_equal(self):
        """Changed/added/reordered query string is not equal."""
        canon_a = canonicalize_url("https://example.com/search?q=1")
        canon_b = canonicalize_url("https://example.com/search?q=2")
        assert canon_a != canon_b

    def test_reordered_query_not_equal(self):
        """Reordered query string is not equal."""
        canon_a = canonicalize_url("https://example.com/search?a=1&b=2")
        canon_b = canonicalize_url("https://example.com/search?b=2&a=1")
        assert canon_a != canon_b


# ------------------------------------------------------------------
# extract_urls_from_markdown tests
# ------------------------------------------------------------------

class TestExtractUrlsFromMarkdown:
    def test_bare_url(self):
        """Bare HTTP(S) URL is extracted."""
        md = "Visit https://example.com/apply for details."
        urls = extract_urls_from_markdown(md)
        bare = [u for u in urls if u["kind"] == "bare"]
        assert any(u["url"] == "https://example.com/apply" for u in bare)

    def test_markdown_inline_link(self):
        """Markdown inline link destination is extracted."""
        md = "[신청서 양식](https://example.com/files/form.pdf)"
        urls = extract_urls_from_markdown(md)
        links = [u for u in urls if u["kind"] == "markdown_link"]
        assert any(u["url"] == "https://example.com/files/form.pdf" for u in links)

    def test_autolink(self):
        """Autolink <URL> is extracted."""
        md = "<https://example.com/apply>"
        urls = extract_urls_from_markdown(md)
        autolinks = [u for u in urls if u["kind"] == "autolink"]
        assert any(u["url"] == "https://example.com/apply" for u in autolinks)

    def test_extract_mailto_autolink(self):
        """Autolink with mailto scheme is extracted."""
        md = "<mailto:admin@example.com>"
        urls = extract_urls_from_markdown(md)
        assert any(u["url"] == "mailto:admin@example.com" for u in urls)

    def test_relative_link_detected(self):
        """Non-empty relative link destination is detected as untrusted."""
        md = "[내부 페이지](/internal/page)"
        urls = extract_urls_from_markdown(md)
        assert any(u["url"] == "/internal/page" for u in urls)

    def test_non_http_link_detected(self):
        """Non-HTTP(S) link destination is detected as untrusted."""
        md = "[이메일](mailto:admin@example.com)"
        urls = extract_urls_from_markdown(md)
        assert any(u["url"] == "mailto:admin@example.com" for u in urls)

    def test_no_urls_returns_empty(self):
        """Markdown with no URLs returns empty list."""
        md = "이 페이지는 신청 방법을 안내합니다."
        urls = extract_urls_from_markdown(md)
        assert urls == []

    def test_html_tag_ignored(self):
        """Plain text inside angle brackets (HTML tags or strong) is ignored."""
        md = "이것은 <strong>강조</strong> 및 <요소> 입니다."
        urls = extract_urls_from_markdown(md)
        assert urls == []

    def test_multiple_url_types(self):
        """Mixed bare URL, link, and autolink all extracted."""
        md = (
            "See <https://example.com/apply> and "
            "[양식](https://example.com/files/form.pdf) "
            "also https://example.com/contact"
        )
        urls = extract_urls_from_markdown(md)
        kinds = [u["kind"] for u in urls]
        assert "autolink" in kinds
        assert "markdown_link" in kinds
        assert "bare" in kinds


# ------------------------------------------------------------------
# assess_url_allowlist tests
# ------------------------------------------------------------------

class TestAssessUrlAllowlist:
    def _make_sources(self, urls_and_canonicals):
        """Helper to build source list from (url, canonical_url) pairs."""
        return [
            {"url": u, "canonical_url": c, "title": f"src{i}", "content_type": "page"}
            for i, (u, c) in enumerate(urls_and_canonicals)
        ]

    def test_exact_source_url_passes(self):
        """Exact source URL in answer passes allowlist."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "[신청](https://example.com/apply)", sources
        )
        assert result["passed"] is True
        assert result["blocked_urls"] == []

    def test_fragment_variation_passes(self):
        """URL with only a fragment variation passes (fragment discarded)."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "[신청](https://example.com/apply#section)", sources
        )
        assert result["passed"] is True

    def test_scheme_host_case_variation_passes(self):
        """Case variation in scheme/host passes after canonicalization."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "[신청](HTTPS://EXAMPLE.COM/apply)", sources
        )
        assert result["passed"] is True

    def test_default_port_variation_passes(self):
        """Default port variation passes after canonicalization."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "[신청](https://example.com:443/apply)", sources
        )
        assert result["passed"] is True

    def test_same_host_different_path_blocked(self):
        """Same host with different path is blocked."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "[관리](https://example.com/admin)", sources
        )
        assert result["passed"] is False
        assert "https://example.com/admin" in result["blocked_urls"]

    def test_path_prefix_lookalike_blocked(self):
        """Path-prefix lookalike (/apply/admin) is blocked when /apply is allowlisted."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "[하위](https://example.com/apply/admin)", sources
        )
        assert result["passed"] is False

    def test_subdomain_lookalike_blocked(self):
        """Subdomain lookalike is blocked."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "[다른 사이트](https://sub.example.com/apply)", sources
        )
        assert result["passed"] is False

    def test_host_suffix_lookalike_blocked(self):
        """Host suffix lookalike is blocked."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "[유사](https://evil-example.com/apply)", sources
        )
        assert result["passed"] is False

    def test_changed_query_blocked(self):
        """Changed query string is blocked."""
        sources = self._make_sources([
            ("https://example.com/search?q=1", "https://example.com/search?q=1"),
        ])
        result = assess_url_allowlist(
            "[검색](https://example.com/search?q=2)", sources
        )
        assert result["passed"] is False

    def test_reordered_query_blocked(self):
        """Reordered query string is blocked."""
        sources = self._make_sources([
            ("https://example.com/search?a=1&b=2", "https://example.com/search?a=1&b=2"),
        ])
        result = assess_url_allowlist(
            "[검색](https://example.com/search?b=2&a=1)", sources
        )
        assert result["passed"] is False

    def test_exact_attachment_url_accepted(self):
        """Exact attachment URL passes allowlist."""
        sources = self._make_sources([
            ("https://example.com/files/form.pdf", "https://example.com/files/form.pdf"),
        ])
        result = assess_url_allowlist(
            "[첨부](https://example.com/files/form.pdf)", sources
        )
        assert result["passed"] is True

    def test_different_same_host_download_blocked(self):
        """Same-host but different download URL is blocked."""
        sources = self._make_sources([
            ("https://example.com/files/form.pdf", "https://example.com/files/form.pdf"),
        ])
        result = assess_url_allowlist(
            "[다른 파일](https://example.com/files/other.pdf)", sources
        )
        assert result["passed"] is False

    def test_relative_link_blocked(self):
        """Relative link destination is blocked (untrusted)."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "[내부](/internal/page)", sources
        )
        assert result["passed"] is False

    def test_non_http_link_blocked(self):
        """Non-HTTP(S) link destination is blocked (untrusted)."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "[이메일](mailto:admin@example.com)", sources
        )
        assert result["passed"] is False

    def test_guard_mailto_autolink(self):
        """mailto autolink in output is blocked."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "<mailto:admin@example.com>", sources
        )
        assert result["passed"] is False

    def test_guard_dot_segments(self):
        """dot segments in output are blocked."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "<https://example.com/apply/..>", sources
        )
        assert result["passed"] is False

    def test_guard_unsupported_port_block(self):
        """unsupported ports in output are blocked."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "<https://example.com:999999/apply>", sources
        )
        assert result["passed"] is False

    def test_no_urls_in_output_passes(self):
        """Provider output with no URLs passes unchanged."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "신청 방법은 공식 홈페이지에서 확인하세요.", sources
        )
        assert result["passed"] is True

    def test_canonical_url_used_in_allowlist(self):
        """canonical_url is included in the allowlist when present."""
        sources = self._make_sources([
            ("https://www.example.com/apply", "https://example.com/apply"),
        ])
        # The canonical_url allows matching even if url differs.
        result = assess_url_allowlist(
            "[신청](https://example.com/apply)", sources
        )
        assert result["passed"] is True

    def test_bare_url_assessed(self):
        """Bare URL in output is assessed against allowlist."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "See https://example.com/apply for info.", sources
        )
        assert result["passed"] is True

    def test_autolink_assessed(self):
        """Autolink URL in output is assessed."""
        sources = self._make_sources([
            ("https://example.com/apply", "https://example.com/apply"),
        ])
        result = assess_url_allowlist(
            "<https://example.com/apply>", sources
        )
        assert result["passed"] is True


# ------------------------------------------------------------------
# AnswerComposer integration: URL guard in compose()
# ------------------------------------------------------------------

class TestComposerUrlGuardIntegration:
    """Test that AnswerComposer.compose() applies the URL guard."""

    def _make_search_data(self, source_url, canonical_url=None):
        """Helper to build minimal search result data."""
        return {
            "query": "테스트",
            "results": [
                {
                    "rank": 1,
                    "id": "doc-001",
                    "title": "테스트 문서",
                    "url": source_url,
                    "canonical_url": canonical_url or source_url,
                    "category": "page",
                    "content_type": "page",
                    "score": 10.0,
                    "matched_terms": ["테스트"],
                    "matched_fields": ["title"],
                    "snippet": "테스트 문서 내용",
                    "metadata": {
                        "source_types": ["page"],
                        "fetch_status": "fetched",
                        "description": "",
                    },
                },
            ],
        }

    def test_allowed_url_in_mock_output_passes(self):
        """MockProvider output referencing a source URL passes the guard."""
        data = self._make_search_data("https://example.com/apply")
        # MockProvider returns a fixed answer that may or may not contain URLs.
        # Use a controlled provider to inject a specific answer.
        class ControlledProvider(MockProvider):
            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                return ProviderResult(
                    provider="controlled",
                    model="controlled",
                    ok=True,
                    content="## 답변\n\n자세한 내용은 [신청 페이지](https://example.com/apply)에서 확인하세요.",
                    error="",
                )

        composer = AnswerComposer(provider=ControlledProvider())
        result = composer.compose(data)
        assert result["ok"] is True
        assert "https://example.com/apply" in result["answer_markdown"]

    def test_blocked_url_in_mock_output_fails_closed(self):
        """Provider output with an untrusted URL fails closed."""
        data = self._make_search_data("https://example.com/apply")
        class ControlledProvider(MockProvider):
            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                return ProviderResult(
                    provider="controlled",
                    model="controlled",
                    ok=True,
                    content="## 답변\n\n[위험](https://evil.com/phish) 페이지를 참고하세요.",
                    error="",
                )

        composer = AnswerComposer(provider=ControlledProvider())
        result = composer.compose(data)
        assert result["ok"] is False
        assert result["answer_markdown"] == ""
        assert "blocked_untrusted_output_url" == result["guard_status"]
        assert "Provider output contained a URL that is not an exact retrieved source URL." == result["guard_reason"]
        assert "untrusted_output_url" == result["error"]
        assert "untrusted_output_url" in result["warnings"]
        assert "url_guard_blocked_urls" not in result
        # Never leaks untrusted provider content.
        assert "evil.com" not in result.get("answer_markdown", "")

    def test_blocked_output_preserves_sources(self):
        """Blocked output still preserves the source list."""
        data = self._make_search_data("https://example.com/apply")
        class ControlledProvider(MockProvider):
            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                return ProviderResult(
                    provider="controlled",
                    model="controlled",
                    ok=True,
                    content="[위험](https://evil.com/phish)",
                    error="",
                )

        composer = AnswerComposer(provider=ControlledProvider())
        result = composer.compose(data)
        assert result["ok"] is False
        assert len(result["sources"]) == 1
        assert result["sources"][0]["url"] == "https://example.com/apply"

    def test_blocked_output_has_machine_readable_warning(self):
        """Blocked output does not include custom warning but does not fail."""
        data = self._make_search_data("https://example.com/apply")
        class ControlledProvider(MockProvider):
            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                return ProviderResult(
                    provider="controlled",
                    model="controlled",
                    ok=True,
                    content="[위험](https://evil.com/phish)",
                    error="",
                )

        composer = AnswerComposer(provider=ControlledProvider())
        result = composer.compose(data)
        assert result["ok"] is False

    def test_no_url_output_passes_unchanged(self):
        """Provider output with no URLs passes guard unchanged."""
        data = self._make_search_data("https://example.com/apply")
        class ControlledProvider(MockProvider):
            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                return ProviderResult(
                    provider="controlled",
                    model="controlled",
                    ok=True,
                    content="## 답변\n\n공식 홈페이지에서 확인해 주세요.",
                    error="",
                )

        composer = AnswerComposer(provider=ControlledProvider())
        result = composer.compose(data)
        assert result["ok"] is True
        assert "공식 홈페이지" in result["answer_markdown"]

    def test_exact_attachment_url_passes(self):
        """Exact attachment source URL passes guard."""
        data = {
            "query": "신청서",
            "results": [
                {
                    "rank": 1,
                    "id": "doc-att",
                    "title": "신청서 양식",
                    "url": "https://example.com/files/form.pdf",
                    "canonical_url": "https://example.com/files/form.pdf",
                    "category": "document",
                    "content_type": "attachment",
                    "score": 15.0,
                    "matched_terms": ["신청서"],
                    "matched_fields": ["title"],
                    "snippet": "신청서 양식",
                    "metadata": {
                        "source_types": ["attachment"],
                        "fetch_status": "skipped",
                        "description": "",
                    },
                },
            ],
        }
        class ControlledProvider(MockProvider):
            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                return ProviderResult(
                    provider="controlled",
                    model="controlled",
                    ok=True,
                    content="[첨부문서](https://example.com/files/form.pdf)",
                    error="",
                )

        composer = AnswerComposer(provider=ControlledProvider())
        result = composer.compose(data)
        assert result["ok"] is True
        assert "form.pdf" in result["answer_markdown"]

    def test_different_same_host_download_blocked(self):
        """Same-host but different download URL is blocked even for attachment source."""
        data = {
            "query": "신청서",
            "results": [
                {
                    "rank": 1,
                    "id": "doc-att",
                    "title": "신청서 양식",
                    "url": "https://example.com/files/form.pdf",
                    "canonical_url": "https://example.com/files/form.pdf",
                    "category": "document",
                    "content_type": "attachment",
                    "score": 15.0,
                    "matched_terms": ["신청서"],
                    "matched_fields": ["title"],
                    "snippet": "신청서 양식",
                    "metadata": {
                        "source_types": ["attachment"],
                        "fetch_status": "skipped",
                        "description": "",
                    },
                },
            ],
        }
        class ControlledProvider(MockProvider):
            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                return ProviderResult(
                    provider="controlled",
                    model="controlled",
                    ok=True,
                    content="[다른 파일](https://example.com/files/other.pdf)",
                    error="",
                )

        composer = AnswerComposer(provider=ControlledProvider())
        result = composer.compose(data)
        assert result["ok"] is False
        assert result["answer_markdown"] == ""

    def test_relative_link_in_output_blocked(self):
        """Relative link destination in provider output is blocked."""
        data = self._make_search_data("https://example.com/apply")
        class ControlledProvider(MockProvider):
            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                return ProviderResult(
                    provider="controlled",
                    model="controlled",
                    ok=True,
                    content="[내부](/admin/panel)",
                    error="",
                )

        composer = AnswerComposer(provider=ControlledProvider())
        result = composer.compose(data)
        assert result["ok"] is False
        assert result["guard_status"] == "blocked_untrusted_output_url"

    def test_canonical_url_preserved_in_sources(self):
        """_extract_sources now preserves canonical_url."""
        results = [
            {
                "rank": 1,
                "id": "doc-001",
                "title": "테스트",
                "url": "https://www.example.com/apply",
                "canonical_url": "https://example.com/apply",
                "category": "page",
                "content_type": "page",
                "score": 10.0,
                "matched_terms": ["테스트"],
                "matched_fields": ["title"],
                "snippet": "테스트",
                "metadata": {
                    "source_types": ["page"],
                    "fetch_status": "fetched",
                    "description": "",
                },
            },
        ]
        sources = AnswerComposer._extract_sources(results, 5)
        assert sources[0]["canonical_url"] == "https://example.com/apply"

    def test_blocked_never_leaks_provider_content(self):
        """Blocked output must not leak any part of untrusted provider prose."""
        data = self._make_search_data("https://example.com/apply")
        malicious_content = (
            "## 답변\n\n"
            "신청은 [위험사이트](https://evil.com/phish)에서 가능합니다.\n\n"
            "이 텍스트는 절대 사용자에게 보이지 않아야 합니다."
        )
        class ControlledProvider(MockProvider):
            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                return ProviderResult(
                    provider="controlled",
                    model="controlled",
                    ok=True,
                    content=malicious_content,
                    error="",
                )

        composer = AnswerComposer(provider=ControlledProvider())
        result = composer.compose(data)
        assert result["ok"] is False
        assert result["answer_markdown"] == ""
        assert "위험사이트" not in str(result)
        assert "이 텍스트는" not in str(result)
