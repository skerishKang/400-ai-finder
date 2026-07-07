"""Requests-based fetch provider — standard HTTP GET using the requests library.

This is the default provider (mimics the existing URLCrawler behavior).
Stage 35: Enhanced header handling with browser-like defaults and 400 retry.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

try:
    import requests as req_lib
    from bs4 import BeautifulSoup
except ImportError:
    req_lib = None  # type: ignore[assignment]
    BeautifulSoup = None  # type: ignore[assignment]

from .base import FetchConfig, FetchProvider, FetchResult

# ---------------------------------------------------------------------------
# Default browser-like headers (Stage 35)
# ---------------------------------------------------------------------------
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_BASE_HEADERS: dict[str, str] = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

_RETRY_HEADERS: dict[str, str] = {
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def _build_headers(user_agent: str) -> dict[str, str]:
    """Build full request headers dict from a User-Agent string."""
    headers = dict(_BASE_HEADERS)
    headers["User-Agent"] = user_agent
    return headers


def _build_retry_headers(user_agent: str) -> dict[str, str]:
    """Build enhanced headers for 400-retry (includes Sec-Fetch-* set)."""
    headers = _build_headers(user_agent)
    headers.update(_RETRY_HEADERS)
    return headers


class RequestsFetchProvider(FetchProvider):
    """Standard HTTP GET fetch provider using 'requests' + BeautifulSoup.

    Stage 35 enhancements:
    - Browser-like default headers (Accept, Accept-Language, Accept-Encoding, etc.)
    - Automatic single retry with enhanced Sec-Fetch-* headers on HTTP 400
    - Configurable via constructor or environment variables
    """

    def __init__(self, timeout: int = 15, user_agent: str | None = None):
        if req_lib is None:
            raise ImportError(
                "The 'requests' library is required for RequestsFetchProvider."
            )
        self.timeout = timeout
        self.user_agent = user_agent or _DEFAULT_USER_AGENT
        self.headers = _build_headers(self.user_agent)

    @staticmethod
    def _split_timeout(timeout: Any) -> tuple[float, float]:
        """Split a timeout into (connect, read) so a single value never blocks both.

        requests accepts ``timeout`` as a single float/int (applied to both
        connect and read) or a tuple ``(connect, read)``. When the upstream
        network refuses to ACK the TCP SYN (e.g. firewalled hosts in offline
        environments), a single ``timeout`` still waits the full budget on the
        connect step. Capping ``connect`` at a small bound (default 5s) keeps
        the worst-case wait bounded even when callers pass a large ``read``
        budget.
        """
        try:
            total = float(timeout)
        except (TypeError, ValueError):
            return (5.0, 15.0)
        if total <= 0:
            return (5.0, 15.0)
        connect = min(5.0, total)
        read = total
        return (connect, read)

    def _request_once(
        self,
        url: str,
        timeout: tuple[float, float],
        headers: dict[str, str] | None = None,
    ) -> Any:
        return req_lib.get(url, headers=headers or self.headers, timeout=timeout)

    def _request_with_legacy_400_retry(
        self,
        url: str,
        timeout: tuple[float, float],
    ) -> Any:
        resp = self._request_once(url, timeout, self.headers)
        if resp.status_code != 400:
            return resp

        retry_headers = _build_retry_headers(self.user_agent)
        try:
            return self._request_once(url, timeout, retry_headers)
        except Exception:
            return resp

    def fetch(
        self,
        url: str,
        config: FetchConfig | None = None,
        **kwargs: Any,
    ) -> FetchResult:
        raw_timeout = config.timeout if config is not None else kwargs.get("timeout", self.timeout)
        timeout = self._split_timeout(raw_timeout)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # --- Validate URL ---
        if not url or not url.startswith(("http://", "https://")):
            return FetchResult(
                url=url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error=f"Invalid URL: must start with http:// or https://",
            )

        # --- HTTP request ---
        if config is None:
            try:
                resp = self._request_with_legacy_400_retry(url, timeout)
            except req_lib.exceptions.Timeout:
                return FetchResult(
                    url=url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error=f"Request timed out after {timeout}s",
                )
            except req_lib.exceptions.RequestException as e:
                return FetchResult(
                    url=url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error=f"Network error: {e}",
                )
            except Exception as e:
                return FetchResult(
                    url=url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error=f"Unexpected error: {e}",
                )
        else:
            attempts = config.max_retries + 1
            resp = None
            for attempt_index in range(attempts):
                try:
                    resp = self._request_with_legacy_400_retry(url, timeout)
                except req_lib.exceptions.Timeout:
                    if attempt_index < config.max_retries:
                        if config.retry_backoff > 0:
                            time.sleep(config.retry_backoff)
                        continue
                    return FetchResult(
                        url=url,
                        ok=False,
                        provider=self.name,
                        fetched_at=now,
                        error=f"Request timed out after {timeout}s",
                    )
                except req_lib.exceptions.RequestException as e:
                    return FetchResult(
                        url=url,
                        ok=False,
                        provider=self.name,
                        fetched_at=now,
                        error=f"Network error: {e}",
                    )
                except Exception as e:
                    return FetchResult(
                        url=url,
                        ok=False,
                        provider=self.name,
                        fetched_at=now,
                        error=f"Unexpected error: {e}",
                    )

                if (
                    resp.status_code in config.retry_on_status
                    and attempt_index < config.max_retries
                ):
                    if config.retry_backoff > 0:
                        time.sleep(config.retry_backoff)
                    continue
                break

        status_code = resp.status_code
        content_type = resp.headers.get("Content-Type", "")
        final_url = resp.url

        # --- Handle HTTP errors ---
        if status_code >= 400:
            return FetchResult(
                url=final_url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                status_code=status_code,
                content_type=content_type,
                error=f"HTTP {status_code}",
            )

        # --- Parse HTML ---
        if "text/html" not in content_type.lower():
            return FetchResult(
                url=final_url,
                ok=True,
                provider=self.name,
                fetched_at=now,
                status_code=status_code,
                content_type=content_type,
                text=resp.text,
                error="",
            )

        # Handle encoding
        if resp.encoding == "ISO-8859-1":
            resp.encoding = resp.apparent_encoding

        try:
            soup = BeautifulSoup(resp.text, "html.parser")

            # Title
            title = ""
            title_tag = soup.title
            if title_tag:
                title = title_tag.get_text().strip()

            # Description
            description = ""
            desc_tag = soup.find(
                "meta", attrs={"name": lambda x: x and x.lower() == "description"}
            )
            if desc_tag and desc_tag.get("content"):
                description = desc_tag.get("content").strip()
            else:
                og_desc = soup.find("meta", attrs={"property": "og:description"})
                if og_desc and og_desc.get("content"):
                    description = og_desc.get("content").strip()

            # Clean text
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            raw_text = soup.get_text(separator="\n")
            text_lines = [line.strip() for line in raw_text.splitlines()]
            clean_text = "\n".join(line for line in text_lines if line)

            # Links
            links = []
            seen_urls = set()
            for a_tag in soup.find_all("a"):
                href = a_tag.get("href")
                if not href:
                    continue
                href_lower = href.lower().strip()
                if href_lower.startswith(
                    ("javascript:", "mailto:", "tel:", "sms:")
                ) or href_lower == "#":
                    continue
                if href not in seen_urls:
                    seen_urls.add(href)
                    links.append({"text": a_tag.get_text().strip() or href, "url": href})

            return FetchResult(
                url=final_url,
                ok=True,
                provider=self.name,
                fetched_at=now,
                status_code=status_code,
                content_type=content_type,
                html=resp.text,
                text=clean_text,
                title=title,
                description=description,
                links=links,
                error="",
            )

        except Exception as e:
            return FetchResult(
                url=final_url,
                ok=True,
                provider=self.name,
                fetched_at=now,
                status_code=status_code,
                content_type=content_type,
                html=resp.text,
                text=resp.text,
                error=f"HTML parsing error: {e}",
            )

    @property
    def name(self) -> str:
        return "requests"
