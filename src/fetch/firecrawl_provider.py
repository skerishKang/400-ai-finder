"""Firecrawl fetch provider — uses the Firecrawl API to scrape web pages.

Endpoint: POST {base_url}/v1/scrape
Formats requested: markdown, html, links

#1295 Dual URL Security Boundaries:
1. Acquisition target URL (body.url):
   Validated against the public egress policy before any request preparation
   or network dispatch. Prohibited targets fail closed without requiring an
   API key and are never placed in a request payload.
2. Provider service endpoint (base_url / FIRECRAWL_BASE_URL):
   The socket destination where `Authorization: Bearer <API_KEY>` is sent.
   Ordinary operation is pinned strictly to the reviewed official Firecrawl
   endpoint (https://api.firecrawl.dev). Unapproved arbitrary/private endpoints
   fail closed before socket dispatch (POST count = 0), preventing credential
   transmission. An explicit test seam (allow_test_endpoint=True) is available
   for unit test harnesses only.

Downstream sourceURL validation:
The effective/final URL (metadata.sourceURL) is validated against both the
#1294 acquisition policy and the #1295 egress policy before being trusted.
Firecrawl internal redirect chains are not observable by this client, so
identical per-hop redirect SSRF prevention as RequestsFetchProvider is NOT
claimed.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

try:
    import requests as req_lib
except ImportError:
    req_lib = None  # type: ignore[assignment]

from .base import FetchProvider, FetchResult
from .egress_policy import PublicEgressPolicy, is_valid_firecrawl_service_endpoint


class FirecrawlFetchProvider(FetchProvider):
    """Fetch provider using Firecrawl's /v1/scrape endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        egress_policy: PublicEgressPolicy | None = None,
        allow_test_endpoint: bool = False,
    ):
        if req_lib is None:
            raise ImportError(
                "The 'requests' library is required for FirecrawlFetchProvider."
            )

        if api_key is not None:
            self._api_key = api_key
        else:
            self._api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        self._base_url = (
            base_url
            or os.environ.get("FIRECRAWL_BASE_URL", "")
            or "https://api.firecrawl.dev"
        )
        self._timeout = timeout or _int_env("FIRECRAWL_TIMEOUT", 60)
        self._egress_policy = egress_policy if egress_policy is not None else PublicEgressPolicy()
        self._allow_test_endpoint = allow_test_endpoint

    def fetch(self, url: str, **kwargs: Any) -> FetchResult:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        egress_policy = kwargs.get("egress_policy", self._egress_policy)
        acquisition_policy = kwargs.get("acquisition_policy", None)

        # --- Validate URL scheme ---
        if not url or not url.startswith(("http://", "https://")):
            return FetchResult(
                url=url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error="Invalid URL: must start with http:// or https://",
            )

        # --- Boundary A: Validate acquisition target URL (#1295) ---
        if egress_policy is not None and not egress_policy.is_authorized(url):
            return FetchResult(
                url=url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error="Target URL rejected by public egress policy",
            )

        if acquisition_policy is not None and not acquisition_policy.is_authorized(url):
            return FetchResult(
                url=url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error="Target URL rejected by acquisition policy",
            )

        # --- Boundary B: Validate provider service endpoint (#1295) ---
        is_valid_endpoint, endpoint_err = is_valid_firecrawl_service_endpoint(
            self._base_url, allow_test_endpoint=self._allow_test_endpoint
        )
        if not is_valid_endpoint:
            return FetchResult(
                url=url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error=f"Firecrawl service endpoint validation failed: {endpoint_err}",
            )

        # --- Validate API key before network dispatch ---
        if not self._api_key:
            return FetchResult(
                url=url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error=(
                    "Firecrawl API key is not configured. "
                    "Set FIRECRAWL_API_KEY environment variable."
                ),
            )

        # --- Build request ---
        endpoint = f"{self._base_url.rstrip('/')}/v1/scrape"
        timeout = kwargs.get("timeout", self._timeout)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "url": url,
            "formats": ["markdown", "html", "links"],
        }

        try:
            # #1295 — credential-bearing service transport. The Bearer API key
            # is sent to the validated service endpoint only. A dedicated,
            # reviewed Session with ``trust_env=False`` ensures the dispatch
            # does NOT inherit ambient proxy settings (HTTP_PROXY / HTTPS_PROXY
            # / ALL_PROXY) or ~/.netrc credentials from the environment.
            with req_lib.Session() as session:
                session.trust_env = False
                resp = session.post(
                    endpoint, headers=headers, json=body, timeout=timeout
                )
                # Handle HTTP-level errors
                if resp.status_code >= 400:
                    try:
                        err_data: dict[str, Any] = resp.json()
                        err_msg = err_data.get("error", f"HTTP {resp.status_code}")
                    except (json.JSONDecodeError, ValueError, AttributeError):
                        err_msg = f"HTTP {resp.status_code}"
                    return FetchResult(
                        url=url,
                        ok=False,
                        provider=self.name,
                        fetched_at=now,
                        status_code=resp.status_code,
                        error=err_msg,
                    )
                data: dict[str, Any] = resp.json()
        except req_lib.exceptions.Timeout:
            return FetchResult(
                url=url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error=f"Firecrawl request timed out after {timeout}s. "
                      "Try increasing FIRECRAWL_TIMEOUT.",
            )
        except req_lib.exceptions.RequestException as e:
            return FetchResult(
                url=url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error=f"Firecrawl request failed: {e}",
            )
        except json.JSONDecodeError:
            return FetchResult(
                url=url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error="Firecrawl returned invalid JSON response.",
            )

        # --- Parse response ---
        return self._parse_response(
            data,
            url,
            now,
            egress_policy=egress_policy,
            acquisition_policy=acquisition_policy,
        )

    def _parse_response(
        self,
        data: dict[str, Any],
        original_url: str,
        now: str,
        egress_policy: Any = None,
        acquisition_policy: Any = None,
    ) -> FetchResult:
        success = data.get("success", False)
        if not success:
            error_msg = data.get("error", "Unknown Firecrawl error")
            return FetchResult(
                url=original_url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error=error_msg,
                raw=data,
            )

        # Extract data section
        d = data.get("data")
        if not d or not isinstance(d, dict):
            return FetchResult(
                url=original_url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error="Firecrawl response missing 'data' field.",
                raw=data,
            )

        # Check for empty/meaningless data
        has_content = bool(d.get("markdown") or d.get("html") or d.get("text"))
        if not has_content:
            return FetchResult(
                url=original_url,
                ok=True,
                provider=self.name,
                fetched_at=now,
                status_code=200,
                error="Firecrawl returned empty content.",
                raw=data,
            )

        metadata = d.get("metadata", {}) or {}
        source_url = metadata.get("sourceURL")
        if source_url:
            # #1294 / #1295: validate downstream sourceURL before trusting
            if acquisition_policy is not None and not acquisition_policy.is_authorized(source_url):
                return FetchResult(
                    url=original_url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error="Firecrawl returned out-of-scope sourceURL rejected by acquisition policy",
                    raw=data,
                )
            if egress_policy is not None and not egress_policy.is_authorized(source_url):
                return FetchResult(
                    url=original_url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error="Firecrawl returned prohibited sourceURL rejected by public egress policy",
                    raw=data,
                )
            final_url = source_url
        else:
            final_url = original_url

        # Parse links: Firecrawl returns string list, convert to dict list
        raw_links = d.get("links", []) or []
        links: list[dict[str, str]] = []
        if isinstance(raw_links, list):
            for lnk in raw_links:
                if isinstance(lnk, str):
                    links.append({"text": lnk, "url": lnk})
                elif isinstance(lnk, dict):
                    links.append({
                        "text": lnk.get("text", lnk.get("url", "")),
                        "url": lnk.get("url", ""),
                    })

        return FetchResult(
            url=final_url,
            ok=True,
            provider=self.name,
            fetched_at=now,
            status_code=200,
            content_type="text/html",
            markdown=d.get("markdown", "") or "",
            html=d.get("html", "") or "",
            text=d.get("markdown", d.get("html", "")) or "",
            title=metadata.get("title", "") or "",
            description=metadata.get("description", "") or "",
            links=links,
            raw=data,
        )

    @property
    def name(self) -> str:
        return "firecrawl"


def _int_env(key: str, default: int) -> int:
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default
