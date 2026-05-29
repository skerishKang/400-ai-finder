"""Tests for the diagnostics-based crawl strategy router."""

from __future__ import annotations

import json
import pytest

from src.strategy.strategy_router import (
    StrategyRouter,
    route_strategy,
    STATIC_HTML_OK,
    HEADER_SENSITIVE_OK,
    WAF_OR_BLOCK_RISK,
    JS_RENDERING_RISK,
    FRAME_SITE_RISK,
    LEGACY_BOARD_SITE,
    ATTACHMENT_HEAVY_SITE,
    SEARCH_OR_SITEMAP_NEEDED,
    UNKNOWN_OR_FAILED,
)


# ------------------------------------------------------------------
# Helpers: build minimal diagnostics dicts for each scenario
# ------------------------------------------------------------------


def _make_diag(
    *,
    classifications: list[str] | None = None,
    ok: bool = True,
    title: str = "Test Site",
    text_length: int = 5000,
    html_analysis: dict | None = None,
    status: str = "ok",
    force_classifications: list[str] | None = None,
) -> dict:
    """Build a minimal diagnostics dict for testing.

    Args:
        classifications: If None, defaults to [STATIC_HTML_OK] (simulating normal
            diagnostics output). Pass an empty list via force_classifications to
            test the no-classification fallback.
        force_classifications: If set, used verbatim (even if empty) to bypass the
            ``classifications or [...]`` coercion.
    """
    ha = html_analysis or {
        "signals": [],
        "internal_links": 50,
        "external_links": 10,
        "document_links": 0,
        "board_matches": 0,
        "php_legacy_hits": 0,
        "menu_keyword_hits": 5,
        "frame_count": 0,
        "iframe_count": 0,
        "script_count": 10,
        "javascript_href_count": 0,
        "encoding": "UTF-8",
    }

    provider_data: dict = {
        "provider": "requests",
        "status": status,
        "ok": ok,
        "status_code": 200 if ok else 0,
        "title": title,
        "text_length": text_length,
        "html_length": text_length * 10,
        "link_count": ha["internal_links"] + ha["external_links"],
        "error": "",
        "signals": ha.get("signals", []),
        "html_analysis": ha,
    }

    return {
        "url": "https://example.com/",
        "fetched_at": "2026-05-29T06:00:00Z",
        "timeout": 15,
        "provider_count": 1,
        "providers": {"requests": provider_data},
        "signals": ha.get("signals", []),
        "classifications": force_classifications if force_classifications is not None else (classifications or [STATIC_HTML_OK]),
    }


def _make_bukgu_diag() -> dict:
    """Simulate the Stage 10D Bukgu diagnostics result."""
    ha = {
        "signals": ["legacy_board_site", "php_legacy_site"],
        "internal_links": 485,
        "external_links": 248,
        "document_links": 0,
        "board_matches": 42,
        "php_legacy_hits": 35,
        "menu_keyword_hits": 32,
        "frame_count": 0,
        "iframe_count": 0,
        "script_count": 19,
        "javascript_href_count": 0,
        "encoding": "UTF-8",
    }
    provider_data: dict = {
        "provider": "requests",
        "status": "ok",
        "ok": True,
        "status_code": 200,
        "title": "광주광역시 북구",
        "text_length": 7744,
        "html_length": 130344,
        "link_count": 585,
        "error": "",
        "signals": ["legacy_board_site", "php_legacy_site"],
        "html_analysis": ha,
    }
    return {
        "url": "https://bukgu.gwangju.kr/",
        "fetched_at": "2026-05-29T06:00:00Z",
        "timeout": 15,
        "provider_count": 1,
        "providers": {"requests": provider_data},
        "signals": ["legacy_board_site", "php_legacy_site"],
        "classifications": [LEGACY_BOARD_SITE],
    }


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestStrategyRouter:
    """Test suite for StrategyRouter."""

    def test_static_html_ok(self):
        """1. STATIC_HTML_OK → requests, homepage_map, sitemap."""
        diag = _make_diag(classifications=[STATIC_HTML_OK])
        result = StrategyRouter(diag).route()

        assert result["recommended_provider"] == "requests"
        assert result["crawl_order"] == ["homepage_map", "document_index", "keyword_search"]
        assert result["use_sitemap"] is True
        assert result["use_menu_mapping"] is True
        assert result["use_document_index"] is True
        assert result["needs_browser_provider"] is False
        assert len(result["reason_summary"]) > 0

    def test_header_sensitive_ok(self):
        """2. HEADER_SENSITIVE_OK → requests, browser candidate."""
        diag = _make_diag(classifications=[HEADER_SENSITIVE_OK])
        result = StrategyRouter(diag).route()

        assert result["recommended_provider"] == "requests"
        assert result["use_sitemap"] is True
        assert result["use_internal_search"] is True
        assert result["needs_browser_provider"] is True
        assert len(result["reason_summary"]) > 0

    def test_legacy_board_site(self):
        """3. LEGACY_BOARD_SITE → requests, homepage_map + document_index."""
        diag = _make_diag(classifications=[LEGACY_BOARD_SITE])
        result = StrategyRouter(diag).route()

        assert result["recommended_provider"] == "requests"
        assert result["use_document_index"] is True
        assert result["use_menu_mapping"] is True
        assert result["needs_browser_provider"] is False
        assert "게시판" in result["reason_summary"]
        assert len(result["reason_summary"]) > 0

    def test_attachment_heavy(self):
        """4. ATTACHMENT_HEAVY_SITE → document_index top priority."""
        diag = _make_diag(classifications=[ATTACHMENT_HEAVY_SITE])
        result = StrategyRouter(diag).route()

        assert result["recommended_provider"] == "requests"
        assert result["crawl_order"][0] == "document_index"
        assert result["use_document_index"] is True
        assert "hwp" in result["reason_summary"] or "문서" in result["reason_summary"]
        assert len(result["reason_summary"]) > 0

    def test_search_or_sitemap_needed(self):
        """5. SEARCH_OR_SITEMAP_NEEDED → sitemap, internal_search."""
        diag = _make_diag(classifications=[SEARCH_OR_SITEMAP_NEEDED])
        result = StrategyRouter(diag).route()

        assert result["use_sitemap"] is True
        assert result["use_internal_search"] is True
        assert result["use_menu_mapping"] is False
        assert result["crawl_order"][0] == "keyword_search"
        assert len(result["reason_summary"]) > 0

    def test_js_rendering_risk(self):
        """6. JS_RENDERING_RISK → needs_browser_provider true."""
        diag = _make_diag(classifications=[JS_RENDERING_RISK])
        result = StrategyRouter(diag).route()

        assert result["needs_browser_provider"] is True
        assert result["use_internal_search"] is True
        assert result["use_menu_mapping"] is False
        assert len(result["reason_summary"]) > 0

    def test_frame_risk(self):
        """7. FRAME_SITE_RISK → needs_browser_provider true."""
        diag = _make_diag(classifications=[FRAME_SITE_RISK])
        result = StrategyRouter(diag).route()

        assert result["needs_browser_provider"] is True
        assert "frame" in result["reason_summary"].lower()
        assert len(result["reason_summary"]) > 0

    def test_waf_or_block_risk(self):
        """8. WAF_OR_BLOCK_RISK → browser provider candidate, risk flag."""
        diag = _make_diag(classifications=[WAF_OR_BLOCK_RISK])
        result = StrategyRouter(diag).route()

        assert result["needs_browser_provider"] is True
        assert WAF_OR_BLOCK_RISK in result["risk_flags"]
        assert len(result["reason_summary"]) > 0

    def test_unknown_or_failed(self):
        """9. UNKNOWN_OR_FAILED → fallback order."""
        diag = _make_diag(classifications=[UNKNOWN_OR_FAILED], ok=False, status="error")
        result = StrategyRouter(diag).route()

        assert result["needs_browser_provider"] is True
        assert result["use_sitemap"] is True
        assert result["use_internal_search"] is True
        assert len(result["reason_summary"]) > 0

    def test_bukgu_diagnostics_strategy(self):
        """10. 북구청 진단 shape 기반 전략 — LEGACY_BOARD_SITE."""
        diag = _make_bukgu_diag()
        result = StrategyRouter(diag).route()

        assert result["recommended_provider"] == "requests"
        assert result["crawl_order"] == ["homepage_map", "document_index", "keyword_search"]
        assert result["use_sitemap"] is True
        assert result["use_menu_mapping"] is True
        assert result["use_document_index"] is True
        assert result["needs_browser_provider"] is False
        assert LEGACY_BOARD_SITE in result["risk_flags"]
        # Reason should mention board/php signals
        assert "board" in result["reason_summary"].lower() or "php" in result["reason_summary"].lower()
        assert len(result["reason_summary"]) > 0

    def test_json_serializable(self):
        """11. 출력 결과가 JSON 직렬화 가능."""
        diag = _make_diag(classifications=[STATIC_HTML_OK])
        result = StrategyRouter(diag).route()
        dumped = json.dumps(result, ensure_ascii=False)
        loaded = json.loads(dumped)
        assert loaded == result

    def test_reason_summary_not_empty(self):
        """12. reason_summary가 비어 있지 않음."""
        for cls in [
            STATIC_HTML_OK,
            HEADER_SENSITIVE_OK,
            LEGACY_BOARD_SITE,
            ATTACHMENT_HEAVY_SITE,
            SEARCH_OR_SITEMAP_NEEDED,
            JS_RENDERING_RISK,
            FRAME_SITE_RISK,
            WAF_OR_BLOCK_RISK,
            UNKNOWN_OR_FAILED,
        ]:
            diag = _make_diag(classifications=[cls])
            result = StrategyRouter(diag).route()
            assert len(result["reason_summary"]) > 0, f"Empty reason for {cls}"

    # ------------------------------------------------------------------
    # Additional edge cases
    # ------------------------------------------------------------------

    def test_multiple_classifications_first_priority(self):
        """Multiple classifications: highest-priority one drives strategy."""
        diag = _make_diag(classifications=[LEGACY_BOARD_SITE, ATTACHMENT_HEAVY_SITE])
        result = StrategyRouter(diag).route()

        # LEGACY_BOARD_SITE has higher priority than ATTACHMENT_HEAVY_SITE
        # So crawl_order should start with homepage_map, not document_index
        assert result["crawl_order"] == ["homepage_map", "document_index", "keyword_search"]
        assert result["use_menu_mapping"] is True

    def test_no_classifications_fallback(self):
        """No classifications at all → UNKNOWN_OR_FAILED fallback."""
        diag = _make_diag(force_classifications=[])
        result = StrategyRouter(diag).route()

        assert result["needs_browser_provider"] is True
        assert len(result["reason_summary"]) > 0

    def test_empty_diagnostics(self):
        """Completely empty/weird diagnostics → should not crash."""
        result = StrategyRouter({}).route()

        assert result["recommended_provider"] == "requests"
        assert len(result["risk_flags"]) == 0
        assert len(result["reason_summary"]) > 0

    def test_route_strategy_convenience_function(self):
        """Convenience route_strategy() produces same result as router."""
        diag = _make_diag(classifications=[LEGACY_BOARD_SITE])
        router_result = StrategyRouter(diag).route()
        func_result = route_strategy(diag)
        assert func_result == router_result

    def test_risk_flags_collected(self):
        """Risk flags include all non-trivial classifications."""
        diag = _make_diag(
            classifications=[LEGACY_BOARD_SITE, ATTACHMENT_HEAVY_SITE, WAF_OR_BLOCK_RISK],
        )
        result = StrategyRouter(diag).route()

        assert LEGACY_BOARD_SITE in result["risk_flags"]
        assert ATTACHMENT_HEAVY_SITE in result["risk_flags"]
        assert WAF_OR_BLOCK_RISK in result["risk_flags"]

    def test_waf_classification_includes_risk(self):
        """WAF_OR_BLOCK_RISK should be in risk_flags."""
        diag = _make_diag(classifications=[WAF_OR_BLOCK_RISK, STATIC_HTML_OK])
        result = StrategyRouter(diag).route()

        assert WAF_OR_BLOCK_RISK in result["risk_flags"]
        # Primary strategy driven by WAF_OR_BLOCK_RISK (higher priority)
        assert result["needs_browser_provider"] is True
