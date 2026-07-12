"""SiteDiagnostics — real-site compatibility diagnostics for AI-finder.

Analyzes how well a target website can be ingested by the AI-finder pipeline,
detecting WAF, JS-rendering requirements, legacy board patterns, encoding
issues, and other compatibility signals.
"""

from __future__ import annotations

import os
import re
import json
from datetime import datetime, timezone
from typing import Any

from ..crawler.url_crawler import URLCrawler
from ..fetch import get_fetch_provider, FetchProvider, FetchResult, list_fetch_providers

# ------------------------------------------------------------------
# Classification labels
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
# Patterns
# ------------------------------------------------------------------

BOARD_PATTERNS = re.compile(
    r"/board|/bbs|/list(\.php)?|/view(\.php)?|/article|/notice|"
    r"wr_id=|no=\d|bdId=|board_skin|board_name",
    re.I,
)

MENU_KEYWORDS = re.compile(
    r"메뉴|전체메뉴|종합민원|민원서식|교육접수|정보공개|소통광장|"
    r"열린장|참여마당|알림마당|홈페이지",
    re.I,
)

WAF_BLOCK_PATTERNS = re.compile(
    r"403|406|429|Request Blocked|Access Denied|"
    r"forbidden|denied|blocked|WAF|Security|"
    r"잘못된 요청|차단|접근불가|서비스거부",
    re.I,
)

PHP_LEGACY_PATTERNS = re.compile(r"\.php|\.jsp|\.do\b|bbs/|board/", re.I)

DOCUMENT_EXTENSIONS = {
    "pdf", "hwp", "hwpx", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip",
}


class SiteDiagnostics:
    """Run compatibility diagnostics on a target website URL.

    Args:
        url: The target website URL.
        timeout: Request timeout in seconds (default: 15).
        providers: List of provider names to test. If None, uses ["requests"].
                   Use "all" to test all available providers.
    """

    def __init__(
        self,
        url: str,
        timeout: int = 15,
        providers: list[str] | None = None,
    ):
        self.url = url
        self.timeout = timeout

        if providers == ["all"] or providers is None:
            self.providers = ["requests"]
        else:
            self.providers = providers or ["requests"]

    def run(self) -> dict[str, Any]:
        """Run diagnostics and return a structured report."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        provider_results: dict[str, dict[str, Any]] = {}
        for provider_name in self.providers:
            provider_results[provider_name] = self._diagnose_provider(provider_name)

        # Build signals
        all_signals: list[str] = []
        classifications: list[str] = []

        for pname, pdata in provider_results.items():
            sigs = pdata.get("signals", [])
            all_signals.extend(sigs)
            classifications.extend(self._classify(pdata))

        # Deduplicate classifications (preserve order)
        seen_class = set()
        unique_classifications = []
        for c in classifications:
            if c not in seen_class:
                seen_class.add(c)
                unique_classifications.append(c)

        return {
            "url": self.url,
            "fetched_at": now,
            "timeout": self.timeout,
            "provider_count": len(self.providers),
            "providers": provider_results,
            "signals": list(set(all_signals)),
            "classifications": unique_classifications,
        }

    # ------------------------------------------------------------------
    # Per-provider diagnostics
    # ------------------------------------------------------------------

    def _diagnose_provider(self, provider_name: str) -> dict[str, Any]:
        """Run diagnostics using a specific provider."""
        # Handle Firecrawl with missing API key
        if provider_name == "firecrawl" and not os.environ.get("FIRECRAWL_API_KEY"):
            return {
                "provider": "firecrawl",
                "status": "skipped",
                "reason": "FIRECRAWL_API_KEY not set",
                "ok": False,
                "status_code": "",
                "title": "",
                "text_length": 0,
                "html_length": 0,
                "signals": ["api_key_missing"],
            }

        # Try fetch provider first
        fetch_result = None
        provider_error = ""
        try:
            provider = get_fetch_provider(provider_name)
            fetch_result = provider.fetch(self.url, timeout=self.timeout)
        except Exception as e:
            fetch_result = None
            provider_error = str(e)

        # If fetch failed or was skipped, try URLCrawler as fallback for "requests"
        provider_data: dict[str, Any] = {
            "provider": provider_name,
        }

        if fetch_result is not None and fetch_result.ok:
            # Success path — analyze the fetched content
            signals = self._analyze_fetch_result(fetch_result)
            provider_data.update({
                "status": "ok",
                "ok": True,
                "status_code": fetch_result.status_code,
                "content_type": fetch_result.content_type,
                "final_url": fetch_result.url,
                "title": fetch_result.title,
                "description": fetch_result.description,
                "html_length": len(fetch_result.html) if fetch_result.html else 0,
                "text_length": len(fetch_result.text) if fetch_result.text else 0,
                "link_count": len(fetch_result.links),
                "markdown_length": len(fetch_result.markdown) if fetch_result.markdown else 0,
                "error": "",
                "signals": signals,
            })

            # Additional analysis when HTML is available
            html = fetch_result.html or ""
            if html:
                html_analysis = self._analyze_html(html, self.url)
                provider_data["html_analysis"] = html_analysis
                provider_data["signals"].extend(html_analysis.get("signals", []))
                for field in [
                    "internal_links", "external_links", "document_links",
                    "board_matches", "menu_keyword_hits",
                    "frame_count", "iframe_count", "script_count",
                    "javascript_href_count",
                    "php_legacy_hits", "encoding",
                ]:
                    if field in html_analysis:
                        provider_data[field] = html_analysis[field]

        elif fetch_result is not None:
            # Fetch failed
            provider_data.update({
                "status": "error",
                "ok": False,
                "status_code": getattr(fetch_result, "status_code", ""),
                "error": fetch_result.error,
                "signals": ["fetch_failed"],
            })
        else:
            provider_data.update({
                "status": "error",
                "ok": False,
                "error": provider_error,
                "signals": ["provider_error"],
            })

        # Try URLCrawler as an additional diagnostic path for "requests"
        if provider_name == "requests" and (not fetch_result or not fetch_result.ok or not fetch_result.html):
            try:
                crawler = URLCrawler(timeout=self.timeout)
                analyze_result = crawler.analyze(self.url, max_chars=20000)
                provider_data["crawler_result"] = {
                    "status_code": analyze_result.get("status_code"),
                    "content_type": analyze_result.get("content_type"),
                    "title": analyze_result.get("title"),
                    "text_length": analyze_result.get("stats", {}).get("text_length", 0),
                    "internal_links": analyze_result.get("stats", {}).get("internal_link_count", 0),
                    "external_links": analyze_result.get("stats", {}).get("external_link_count", 0),
                    "document_links": analyze_result.get("stats", {}).get("attachment_count", 0),
                    "errors": analyze_result.get("errors", []),
                }
                # Add crawler-specific signals
                if analyze_result.get("errors"):
                    for err in analyze_result["errors"]:
                        if "timeout" in err.lower():
                            provider_data["signals"].append("crawler_timeout")
                        elif "http" in err.lower():
                            provider_data["signals"].append("crawler_http_error")
            except Exception as e:
                provider_data["crawler_result"] = {"error": str(e)}

        # Deduplicate signals
        provider_data["signals"] = list(set(provider_data.get("signals", [])))
        return provider_data

    # ------------------------------------------------------------------
    # Content analysis
    # ------------------------------------------------------------------

    @staticmethod
    def _analyze_fetch_result(result: FetchResult) -> list[str]:
        """Analyze a FetchResult for basic signals."""
        signals = []

        if result.status_code and int(result.status_code) >= 400:
            signals.append("http_error")

        if result.error and any(
            w in result.error.lower()
            for w in ["timeout", "timed out"]
        ):
            signals.append("timeout")

        if result.error and any(
            b in result.error.lower()
            for b in ["403", "406", "429", "blocked", "denied", "forbidden"]
        ):
            signals.append("waf_or_block")

        # Check for very short text
        text = result.text or result.markdown or ""
        if len(text) < 100:
            signals.append("very_low_text_content")

        return signals

    @staticmethod
    def _analyze_html(html: str, base_url: str) -> dict[str, Any]:
        """Analyze HTML content for compatibility signals."""
        result: dict[str, Any] = {
            "signals": [],
        }

        # --- Encoding ---
        encoding = ""
        meta_charset = re.search(
            r'<meta[^>]+charset\s*=\s*["\']?([^"\'\s>]+)',
            html, re.I,
        )
        if meta_charset:
            encoding = meta_charset.group(1)
        result["encoding"] = encoding
        if encoding and encoding.lower() in ("euc-kr", "euc-jp", "iso-8859-1"):
            result["signals"].append("legacy_encoding")

        # --- Links classification ---
        # Extract all hrefs from HTML
        all_hrefs = re.findall(r'href\s*=\s*["\']([^"\']+)["\']', html, re.I)
        internal_links = 0
        external_links = 0
        document_links = 0
        document_files: list[str] = []
        board_matches = 0
        php_legacy_hits = 0
        menu_keyword_hits = 0

        for href in all_hrefs:
            href_lower = href.lower().strip()
            if href_lower.startswith(("javascript:", "mailto:", "tel:", "#", "data:")):
                continue

            # Document link check
            ext = href_lower.rsplit(".", 1)[-1] if "." in href_lower else ""
            if ext in DOCUMENT_EXTENSIONS:
                document_links += 1
                document_files.append(href)
                continue

            # Internal vs external
            if not href_lower.startswith("http"):
                internal_links += 1
            else:
                external_links += 1

            # Board pattern
            if BOARD_PATTERNS.search(href):
                board_matches += 1

            # PHP / legacy
            if PHP_LEGACY_PATTERNS.search(href):
                php_legacy_hits += 1

        result["internal_links"] = internal_links
        result["external_links"] = external_links
        result["document_links"] = document_links
        result["document_files"] = document_files[:20]  # limit
        result["board_matches"] = board_matches
        result["php_legacy_hits"] = php_legacy_hits

        # --- Menu keywords in text ---
        menu_matches = MENU_KEYWORDS.findall(html)
        menu_keyword_hits = len(menu_matches)
        result["menu_keyword_hits"] = menu_keyword_hits

        # --- Frame / iframe ---
        frame_count = len(re.findall(r'<frame\s', html, re.I))
        iframe_count = len(re.findall(r'<iframe\s', html, re.I))
        result["frame_count"] = frame_count
        result["iframe_count"] = iframe_count
        if frame_count > 0 or iframe_count > 0:
            result["signals"].append("frame_site")

        # --- Script tags ---
        script_count = len(re.findall(r'<script\s', html, re.I))
        result["script_count"] = script_count

        # --- javascript: hrefs ---
        js_href_count = len(re.findall(r'href\s*=\s*["\']javascript:', html, re.I))
        result["javascript_href_count"] = js_href_count

        # --- Signals from HTML analysis ---
        if board_matches >= 3:
            result["signals"].append("legacy_board_site")

        if php_legacy_hits >= 3:
            result["signals"].append("php_legacy_site")

        if menu_keyword_hits == 0 and script_count > 20:
            result["signals"].append("js_rendering_risk")

        if document_links > 10:
            result["signals"].append("attachment_heavy")

        if script_count > 50:
            result["signals"].append("heavy_javascript")

        if menu_keyword_hits == 0:
            result["signals"].append("menu_keywords_missing")

        # Deduplicate signals
        result["signals"] = list(set(result["signals"]))
        return result

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify(provider_data: dict[str, Any]) -> list[str]:
        """Determine classifications from provider diagnostic data."""
        classifications: list[str] = []
        signals = provider_data.get("signals", [])

        if provider_data.get("status") == "skipped":
            return []

        if not provider_data.get("ok", False):
            if "timeout" in signals:
                classifications.append(WAF_OR_BLOCK_RISK)
            elif "waf_or_block" in signals:
                classifications.append(WAF_OR_BLOCK_RISK)
            else:
                classifications.append(UNKNOWN_OR_FAILED)
            return classifications

        # Signals
        if "waf_or_block" in signals:
            classifications.append(WAF_OR_BLOCK_RISK)

        if "js_rendering_risk" in signals:
            classifications.append(JS_RENDERING_RISK)

        if "frame_site" in signals:
            classifications.append(FRAME_SITE_RISK)

        if "legacy_board_site" in signals or "php_legacy_site" in signals:
            classifications.append(LEGACY_BOARD_SITE)

        if "attachment_heavy" in signals:
            classifications.append(ATTACHMENT_HEAVY_SITE)

        if "very_low_text_content" in signals:
            classifications.append(SEARCH_OR_SITEMAP_NEEDED)

        if "menu_keywords_missing" in signals and JS_RENDERING_RISK not in classifications:
            classifications.append(SEARCH_OR_SITEMAP_NEEDED)

        # Default if everything looks clean
        if not classifications:
            title = provider_data.get("title", "")
            text_length = provider_data.get("text_length", 0)
            if title and text_length > 100:
                classifications.append(STATIC_HTML_OK)
            elif title:
                classifications.append(HEADER_SENSITIVE_OK)
            else:
                classifications.append(UNKNOWN_OR_FAILED)

        return classifications


# ------------------------------------------------------------------
# Convenience function
# ------------------------------------------------------------------

def run_diagnostics(
    url: str,
    timeout: int = 15,
    providers: list[str] | None = None,
) -> dict[str, Any]:
    """One-shot convenience function to run site diagnostics."""
    diag = SiteDiagnostics(url=url, timeout=timeout, providers=providers)
    return diag.run()
