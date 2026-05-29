"""Requests-based fetch provider — standard HTTP GET using the requests library.

This is the default provider (mimics the existing URLCrawler behavior).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

try:
    import requests as req_lib
    from bs4 import BeautifulSoup
except ImportError:
    req_lib = None  # type: ignore[assignment]
    BeautifulSoup = None  # type: ignore[assignment]

from .base import FetchProvider, FetchResult


class RequestsFetchProvider(FetchProvider):
    """Standard HTTP GET fetch provider using 'requests' + BeautifulSoup."""

    def __init__(self, timeout: int = 15, user_agent: str | None = None):
        if req_lib is None:
            raise ImportError(
                "The 'requests' library is required for RequestsFetchProvider."
            )
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.headers = {"User-Agent": self.user_agent}

    def fetch(self, url: str, **kwargs: Any) -> FetchResult:
        timeout = kwargs.get("timeout", self.timeout)
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
        try:
            resp = req_lib.get(url, headers=self.headers, timeout=timeout)
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
