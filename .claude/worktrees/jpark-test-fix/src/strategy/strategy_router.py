"""StrategyRouter — diagnostics-based crawl strategy router for AI-finder.

Takes the output of SiteDiagnostics (a dict with classifications, signals, and
per-provider metadata) and produces a structured crawl strategy plan.

This is a pure judgement layer — it does NOT execute any crawl or modify any
existing pipeline component.
"""

from __future__ import annotations

from typing import Any

# ------------------------------------------------------------------
# Classification labels (mirrored from diagnostics for self-containment)
# ------------------------------------------------------------------
STATIC_HTML_OK = "STATIC_HTML_OK"
HEADER_SENSITIVE_OK = "HEADER_SENSITIVE_OK"
WAF_OR_BLOCK_RISK = "WAF_OR_BLOCK_RISK"
JS_RENDERING_RISK = "JS_RENDERING_RISK"
FRAME_SITE_RISK = "FRAME_SITE_RISK"
LEGACY_BOARD_SITE = "LEGACY_BOARD_SITE"
ATTACHMENT_HEAVY_SITE = "ATTACHMENT_HEAVY_SITE"
SEARCH_OR_SITEMAP_NEEDED = "SEARCH_OR_SITEMAP_NEEDED"
UNKNOWN_OR_FAILED = "UNKNOWN_OR_FAILED"

# ------------------------------------------------------------------
# Strategy result shape
# ------------------------------------------------------------------

DEFAULT_CRAWL_ORDER = ["homepage_map", "document_index", "keyword_search"]


def _new_strategy() -> dict[str, Any]:
    """Return a blank strategy dict with default values."""
    return {
        "recommended_provider": "requests",
        "crawl_order": list(DEFAULT_CRAWL_ORDER),
        "use_sitemap": False,
        "use_menu_mapping": False,
        "use_document_index": False,
        "use_internal_search": False,
        "needs_browser_provider": False,
        "risk_flags": [],
        "reason_summary": "",
    }


# ------------------------------------------------------------------
# Rule implementations (one per classification)
# ------------------------------------------------------------------


def _rule_static_html_ok(strategy: dict[str, Any], _diag: dict[str, Any]) -> None:
    """Clean, simple HTML site — requests provider, homepage map first."""
    strategy["recommended_provider"] = "requests"
    strategy["crawl_order"] = ["homepage_map", "document_index", "keyword_search"]
    strategy["use_sitemap"] = True
    strategy["use_menu_mapping"] = True
    strategy["use_document_index"] = True
    strategy["use_internal_search"] = False
    strategy["needs_browser_provider"] = False
    strategy["reason_summary"] = (
        "정적 HTML 사이트 — requests provider로 homepage map 우선 수집, "
        "사이트맵·메뉴·문서 인덱싱을 사용 가능하다."
    )


def _rule_header_sensitive_ok(strategy: dict[str, Any], _diag: dict[str, Any]) -> None:
    """Headers present but text content short — requests provider, browser candidate flagged."""
    strategy["recommended_provider"] = "requests"
    strategy["crawl_order"] = ["homepage_map", "keyword_search", "document_index"]
    strategy["use_sitemap"] = True
    strategy["use_menu_mapping"] = True
    strategy["use_document_index"] = False
    strategy["use_internal_search"] = True
    strategy["needs_browser_provider"] = True
    strategy["reason_summary"] = (
        "헤더 정보는 있으나 본문 텍스트가 부족하다 — requests provider 우선, "
        "내부 검색 및 브라우저 계열 provider를 후보로 고려한다."
    )


def _rule_legacy_board_site(strategy: dict[str, Any], diag: dict[str, Any]) -> None:
    """PHP/board legacy site — homepage_map + document_index priority."""
    # Extract board/php counts for reason
    provider = _first_ok_provider(diag)
    analysis = _get_html_analysis(diag, provider)
    board_matches = analysis.get("board_matches", 0) if analysis else 0
    php_hits = analysis.get("php_legacy_hits", 0) if analysis else 0

    strategy["recommended_provider"] = "requests"
    strategy["crawl_order"] = ["homepage_map", "document_index", "keyword_search"]
    strategy["use_sitemap"] = True
    strategy["use_menu_mapping"] = True
    strategy["use_document_index"] = True
    strategy["use_internal_search"] = False
    strategy["needs_browser_provider"] = False
    strategy["reason_summary"] = (
        f"requests provider가 동작하고 PHP/게시판 패턴이 많아(board={board_matches}, "
        f"php={php_hits}) 메뉴·게시판·문서 인덱싱을 우선 적용한다."
    )


def _rule_attachment_heavy(strategy: dict[str, Any], _diag: dict[str, Any]) -> None:
    """Attachment-heavy site — document_index gets top priority."""
    strategy["recommended_provider"] = "requests"
    strategy["crawl_order"] = ["document_index", "homepage_map", "keyword_search"]
    strategy["use_sitemap"] = True
    strategy["use_menu_mapping"] = True
    strategy["use_document_index"] = True
    strategy["use_internal_search"] = False
    strategy["needs_browser_provider"] = False
    strategy["reason_summary"] = (
        "첨부파일(hwp/pdf/xls 등) 비중이 높다 — 문서 인덱싱을 최우선으로 "
        "수집하고 메뉴 매핑은 보조로 사용한다."
    )


def _rule_search_or_sitemap_needed(strategy: dict[str, Any], _diag: dict[str, Any]) -> None:
    """Sitemap or internal search needed — prioritise sitemap + search."""
    strategy["recommended_provider"] = "requests"
    strategy["crawl_order"] = ["keyword_search", "homepage_map", "document_index"]
    strategy["use_sitemap"] = True
    strategy["use_menu_mapping"] = False
    strategy["use_document_index"] = False
    strategy["use_internal_search"] = True
    strategy["needs_browser_provider"] = False
    strategy["reason_summary"] = (
        "사이트맵·검색 기능이 필요하다 — 사이트맵을 우선 사용하고 "
        "내부 검색을 통해 페이지를 발굴한다."
    )


def _rule_js_rendering_risk(strategy: dict[str, Any], _diag: dict[str, Any]) -> None:
    """JS-heavy or frame-based — needs a browser-level provider."""
    strategy["recommended_provider"] = "requests"
    strategy["crawl_order"] = ["homepage_map", "keyword_search", "document_index"]
    strategy["use_sitemap"] = True
    strategy["use_menu_mapping"] = False
    strategy["use_document_index"] = False
    strategy["use_internal_search"] = True
    strategy["needs_browser_provider"] = True
    strategy["reason_summary"] = (
        "JavaScript 메뉴/렌더링 위험이 감지되었다 — requests provider로 "
        "우선 시도하되, Firecrawl/Playwright 계열 브라우저 provider를 "
        "후보로 준비한다."
    )


def _rule_frame_risk(strategy: dict[str, Any], _diag: dict[str, Any]) -> None:
    """Frame/iframe-based site — needs a browser-level provider."""
    strategy["recommended_provider"] = "requests"
    strategy["crawl_order"] = ["homepage_map", "keyword_search", "document_index"]
    strategy["use_sitemap"] = True
    strategy["use_menu_mapping"] = False
    strategy["use_document_index"] = False
    strategy["use_internal_search"] = True
    strategy["needs_browser_provider"] = True
    strategy["reason_summary"] = (
        "frame/iframe 구조로 구성된 사이트이다 — requests provider로 "
        "우선 시도하되, 브라우저 계열 provider를 후보로 준비한다."
    )


def _rule_waf_or_block_risk(strategy: dict[str, Any], _diag: dict[str, Any]) -> None:
    """WAF/block risk — mark as risk, recommend browser candidate."""
    strategy["recommended_provider"] = "requests"
    strategy["crawl_order"] = ["homepage_map", "keyword_search", "document_index"]
    strategy["use_sitemap"] = True
    strategy["use_menu_mapping"] = False
    strategy["use_document_index"] = False
    strategy["use_internal_search"] = True
    strategy["needs_browser_provider"] = True
    strategy["reason_summary"] = (
        "WAF/차단 위험이 감지되었다 — requests provider가 차단될 수 있으므로 "
        "브라우저 계열 provider를 후보로 준비한다."
    )


def _rule_unknown_or_failed(strategy: dict[str, Any], _diag: dict[str, Any]) -> None:
    """Unknown or all providers failed — suggest a fallback order."""
    strategy["recommended_provider"] = "requests"
    strategy["crawl_order"] = ["homepage_map", "keyword_search", "document_index"]
    strategy["use_sitemap"] = True
    strategy["use_menu_mapping"] = False
    strategy["use_document_index"] = False
    strategy["use_internal_search"] = True
    strategy["needs_browser_provider"] = True
    strategy["reason_summary"] = (
        "사이트 진단이 실패했거나 분류할 수 없다 — requests provider 우선, "
        "사이트맵·내부 검색·브라우저 provider 순서로 fallback을 시도한다."
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _first_ok_provider(diag: dict[str, Any]) -> str:
    """Return the name of the first provider with ok=True, or 'requests'."""
    providers = diag.get("providers", {})
    for pname, pdata in providers.items():
        if pdata.get("ok"):
            return pname
    return "requests"


def _get_html_analysis(diag: dict[str, Any], provider: str) -> dict[str, Any]:
    """Return the html_analysis sub-dict for a given provider, or empty dict."""
    pdata = diag.get("providers", {}).get(provider, {})
    return pdata.get("html_analysis", {})


# ------------------------------------------------------------------
# Classification → rule mapping (priority order)
# ------------------------------------------------------------------

_RULES: list[tuple[str, Any]] = [
    (WAF_OR_BLOCK_RISK, _rule_waf_or_block_risk),
    (JS_RENDERING_RISK, _rule_js_rendering_risk),
    (FRAME_SITE_RISK, _rule_frame_risk),
    (LEGACY_BOARD_SITE, _rule_legacy_board_site),
    (ATTACHMENT_HEAVY_SITE, _rule_attachment_heavy),
    (SEARCH_OR_SITEMAP_NEEDED, _rule_search_or_sitemap_needed),
    (HEADER_SENSITIVE_OK, _rule_header_sensitive_ok),
    (STATIC_HTML_OK, _rule_static_html_ok),
    (UNKNOWN_OR_FAILED, _rule_unknown_or_failed),
]


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


class StrategyRouter:
    """Route site diagnostics results to a crawl strategy plan.

    This is a pure judgement layer — it does NOT execute any crawl or modify
    any existing pipeline component.

    Args:
        diagnostics_result: The output of ``SiteDiagnostics.run()`` — a dict
            containing ``classifications``, ``providers``, and per-provider
            diagnostics.
    """

    def __init__(self, diagnostics_result: dict[str, Any]) -> None:
        self._diag = diagnostics_result
        self._classifications: list[str] = diagnostics_result.get("classifications", [])

    def route(self) -> dict[str, Any]:
        """Produce a crawl strategy plan based on the diagnostics result.

        Returns:
            A dict with the following fields:
                - recommended_provider (str)
                - crawl_order (list[str])
                - use_sitemap (bool)
                - use_menu_mapping (bool)
                - use_document_index (bool)
                - use_internal_search (bool)
                - needs_browser_provider (bool)
                - risk_flags (list[str])
                - reason_summary (str)
        """
        strategy = _new_strategy()

        # Apply rules in priority order — first match wins for the core strategy
        matched = False
        for classification, rule_fn in _RULES:
            if classification in self._classifications:
                rule_fn(strategy, self._diag)
                matched = True
                break

        if not matched:
            _rule_unknown_or_failed(strategy, self._diag)

        # Collect risk flags from non-primary classifications
        risk_flags: list[str] = []
        for classification in self._classifications:
            if classification not in (
                STATIC_HTML_OK,
                HEADER_SENSITIVE_OK,
                UNKNOWN_OR_FAILED,
            ):
                if classification != self._classifications[0]:
                    risk_flags.append(classification)
                else:
                    risk_flags.append(classification)

        strategy["risk_flags"] = risk_flags

        # If the primary classification has a risk note, fold it in
        # (risk_flags always include the primary if it's a risk class)
        strategy["risk_flags"] = list(dict.fromkeys(risk_flags))  # dedup preserve order

        return strategy


# ------------------------------------------------------------------
# Convenience function
# ------------------------------------------------------------------


def route_strategy(diagnostics_result: dict[str, Any]) -> dict[str, Any]:
    """One-shot convenience wrapper around StrategyRouter.

    Args:
        diagnostics_result: The output of ``SiteDiagnostics.run()``.

    Returns:
        A crawl strategy plan dict.
    """
    router = StrategyRouter(diagnostics_result)
    return router.route()
