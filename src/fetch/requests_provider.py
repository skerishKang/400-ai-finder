"""Requests-based fetch provider — standard HTTP GET using the requests library.

This is the default provider (mimics the existing URLCrawler behavior).
Stage 35: Enhanced header handling with browser-like defaults and 400 retry.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

try:
    import requests as req_lib
    from bs4 import BeautifulSoup
except ImportError:
    req_lib = None  # type: ignore[assignment]
    BeautifulSoup = None  # type: ignore[assignment]

from urllib.parse import urlparse

from .base import FetchConfig, FetchProvider, FetchResult
from .egress_policy import PublicEgressPolicy

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

# ---------------------------------------------------------------------------
# #1294 acquisition-scope redirect containment and #1295 public egress policy
# ---------------------------------------------------------------------------
# When an acquisition policy is supplied, redirects are followed manually so
# the *next* target can be host-authorized BEFORE any request is dispatched to
# it. ``requests``' built-in ``allow_redirects=True`` would otherwise follow an
# external redirect first and only reveal the effective URL afterwards.
_MAX_REDIRECTS = 10

_REDIRECT_SCOPE_BLOCKED = object()
_EGRESS_POLICY_BLOCKED = object()
_REDIRECT_LOOP_EXCEEDED = object()
_REDIRECT_MALFORMED_LOCATION = object()

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


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

    def __init__(
        self,
        timeout: int = 15,
        user_agent: str | None = None,
        egress_policy: PublicEgressPolicy | None = None,
    ):
        if req_lib is None:
            raise ImportError(
                "The 'requests' library is required for RequestsFetchProvider."
            )
        self.timeout = timeout
        self.user_agent = user_agent or _DEFAULT_USER_AGENT
        self.headers = _build_headers(self.user_agent)
        self.egress_policy = egress_policy

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
        timeout: tuple[float, float] | float | int,
        headers: dict[str, str] | None = None,
        allow_redirects: bool = True,
    ) -> Any:
        # Pass headers verbatim. ``None`` falls back to the browser-like
        # defaults; an explicit (possibly empty) dict is sent as-is so that
        # ``headers={}`` does NOT merge with or replace defaults. ``timeout``
        # may be a scalar (legacy transport) or a (connect, read) tuple.
        # ``allow_redirects`` is only forwarded when disabled (the #1294 manual
        # redirect containment loop); the default path keeps the historical
        # call signature so existing callers/transports are unchanged.
        request_kwargs: dict[str, Any] = {
            "headers": self.headers if headers is None else headers,
            "timeout": timeout,
        }
        if not allow_redirects:
            request_kwargs["allow_redirects"] = False
        return req_lib.get(url, **request_kwargs)

    def _origin_key(self, url: str) -> tuple[str, str, int]:
        """Return (scheme, host, port) triple for origin comparison.

        Port is the effective port (default 80 for http, 443 for https)
        when no explicit port is present.
        """
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        host = parsed.hostname.lower() if parsed.hostname else ""
        explicit_port = parsed.port
        if explicit_port is not None:
            port = explicit_port
        else:
            port = 443 if scheme == "https" else 80
        return (scheme, host, port)

    def _fetch_with_scope(
        self,
        url: str,
        timeout: tuple[float, float] | float | int,
        headers: dict[str, str],
        policy: Any,
        config: FetchConfig | None = None,
        egress_policy: Any = None,
    ) -> Any:
        """Follow redirects with per-hop acquisition host and egress authorization.

        #1294: dispatch to a 3xx ``Location`` only after the *next* target has
        been authorized by the frozen acquisition policy. Relative Locations
        are resolved against the current URL before authorization. Every next
        target and the final URL must be in-scope; undeclared hosts are never
        requested (fail closed). Redirect count is bounded by ``_MAX_REDIRECTS``
        so loops fail closed instead of hanging.

        #1295: egress policy is verified at each hop before socket dispatch.
        Redirects from public targets to private/link-local/loopback destinations
        fail closed before the second request.

        Uses a ``requests.Session`` across all hops so that cookies set during
        a same-site redirect (``Set-Cookie``) are carried to the next hop,
        preserving the same cookie/session continuity that ``requests`` native
        redirect following provides.

        #1294 V2 — credential safety boundary is the *origin*
        (scheme + normalized hostname + effective port), not just the host.
        ``Authorization`` and ``Proxy-Authorization`` are stripped whenever
        the origin changes (including scheme downgrade https->http or port
        change), not only on cross-host redirects.

        #1294 V2 — explicit ``Cookie`` header forwarded by the caller is
        stripped before each redirect hop so that the Session cookie jar
        reconstructs cookies for the target domain/path/secure rules instead
        of blindly copying a raw header across origins.

        #1294 V2 — session default headers are cleared before applying the
        caller-provided headers dict so that ``headers={}`` is truly empty
        (no unintentional merge of ``requests`` library defaults).

        #1294 V2 — the Session is closed deterministically via a ``with``
        block (context manager).

        #1294 V2 — the optional ``config`` parameter preserves legacy 400
        retry and FetchConfig retry semantics in the scoped path.
        """
        ep = egress_policy if egress_policy is not None else self.egress_policy
        if ep is not None and not ep.is_authorized(url):
            return _EGRESS_POLICY_BLOCKED
        if policy is not None and not policy.is_authorized(url):
            return _REDIRECT_SCOPE_BLOCKED

        with req_lib.Session() as session:
            session.headers.clear()
            session.headers.update(headers)

            current_url = url
            for hop_index in range(_MAX_REDIRECTS + 1):
                resp = session.get(
                    current_url, timeout=timeout, allow_redirects=False
                )
                if resp.status_code not in _REDIRECT_STATUSES:
                    break

                # #1294 V2: strip explicit Cookie header from session headers
                # before redirect hop so the session cookie jar (not raw
                # header forwarding) governs next-hop cookies.
                session.headers.pop("Cookie", None)

                location = resp.headers.get("Location")
                if not location:
                    return resp
                try:
                    next_url = urljoin(current_url, location)
                except ValueError:
                    return _REDIRECT_MALFORMED_LOCATION

                # #1294 host scope check
                if policy is not None and not policy.is_authorized(next_url):
                    return _REDIRECT_SCOPE_BLOCKED

                # #1295 SSRF-safe public egress check
                if ep is not None and not ep.is_authorized(next_url):
                    return _EGRESS_POLICY_BLOCKED

                # #1294 V2: origin-bound credential safety.
                # Compare exact origin (scheme + host + port), not just host.
                current_origin = self._origin_key(current_url)
                next_origin = self._origin_key(next_url)
                if current_origin != next_origin:
                    session.headers.pop("Authorization", None)
                    session.headers.pop("Proxy-Authorization", None)

                current_url = next_url
            else:
                return _REDIRECT_LOOP_EXCEEDED

        # --- Non-redirect response: apply retry logic when config is provided
        if config is None:
            # Legacy 400 retry (mirrors _request_with_legacy_400_retry)
            if resp.status_code == 400:
                # #1295: re-check egress policy before retry dispatch
                if ep is None or ep.is_authorized(current_url):
                    retry_headers = _build_retry_headers(self.user_agent)
                    try:
                        retry_resp = self._request_once(
                            current_url, timeout, retry_headers, allow_redirects=False
                        )
                        resp = retry_resp
                    except Exception:
                        pass
        else:
            # FetchConfig retry on status
            attempts = config.max_retries + 1
            for attempt_index in range(attempts):
                if resp.status_code not in config.retry_on_status:
                    break
                if attempt_index >= config.max_retries:
                    break
                # #1295: re-check egress policy before retry dispatch
                if ep is not None and not ep.is_authorized(current_url):
                    return _EGRESS_POLICY_BLOCKED
                if config.retry_backoff > 0:
                    time.sleep(config.retry_backoff)
                try:
                    resp = self._request_once(
                        current_url, timeout, self.headers, allow_redirects=False
                    )
                except req_lib.exceptions.Timeout:
                    if attempt_index < config.max_retries:
                        if config.retry_backoff > 0:
                            time.sleep(config.retry_backoff)
                        continue
                    break
                except Exception:
                    break

            return resp

        return resp

    def _request_with_legacy_400_retry(
        self,
        url: str,
        timeout: tuple[float, float],
        egress_policy: Any = None,
    ) -> Any:
        ep = egress_policy if egress_policy is not None else self.egress_policy
        resp = self._request_once(url, timeout, self.headers)
        if resp.status_code != 400:
            return resp

        # #1295: re-check egress policy before retry dispatch
        if ep is not None and not ep.is_authorized(url):
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
        compatibility_mode = kwargs.get("compatibility_mode", False)
        legacy_transport = bool(kwargs.get("legacy_transport", False))
        acquisition_policy = kwargs.get("acquisition_policy", None)
        egress_policy = kwargs.get("egress_policy", self.egress_policy)
        if compatibility_mode:
            # Call-arg timeout > config.timeout > constructor timeout.
            raw_timeout = kwargs.get(
                "timeout", config.timeout if config is not None else self.timeout
            )
        else:
            raw_timeout = config.timeout if config is not None else kwargs.get("timeout", self.timeout)
        # The legacy transport is an opt-in refinement of the compatibility path
        # only: it keeps the caller's scalar timeout verbatim (mirroring the
        # original direct-requests fallback) instead of the split (connect, read)
        # tuple. When not set, the existing split-timeout behavior is preserved.
        if compatibility_mode and legacy_transport:
            timeout = raw_timeout
        else:
            timeout = self._split_timeout(raw_timeout)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # --- Validate URL ---
        if not url or not url.startswith(("http://", "https://")):
            return FetchResult(
                url=url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error="Invalid URL: must start with http:// or https://",
            )

        if compatibility_mode:
            # forwarding kwargs minus timeout (passed positionally above) and
            # legacy_transport (already consumed as a positional flag).
            kwargs.pop("timeout", None)
            kwargs.pop("legacy_transport", None)
            kwargs.pop("acquisition_policy", None)
            kwargs.pop("egress_policy", None)
            return self._fetch_compatibility(
                url, timeout, now, legacy_transport=legacy_transport,
                acquisition_policy=acquisition_policy,
                egress_policy=egress_policy, **kwargs
            )

        # --- HTTP request ---
        if acquisition_policy is not None or egress_policy is not None:
            # #1294: bounded manual redirect following with pre-dispatch host
            # authorization. A 3xx next target is requested only when it is
            # inside the frozen acquisition scope; undeclared hosts are never
            # dispatched to. Loops exceed the bound and fail closed.
            # #1295: bounded redirect hops also enforce public egress policy
            # per hop before socket dispatch.
            # Uses ``requests.Session`` for cookie/session continuity across
            # redirect hops and strips credential-bearing headers (e.g.
            # ``Authorization``, ``Proxy-Authorization``) on cross-host hops.
            resp = self._fetch_with_scope(
                url,
                timeout,
                self.headers,
                acquisition_policy,
                config=config,
                egress_policy=egress_policy,
            )
            if resp is _EGRESS_POLICY_BLOCKED:
                return FetchResult(
                    url=url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error="Redirect to prohibited destination rejected by public egress policy",
                )
            if resp is _REDIRECT_SCOPE_BLOCKED:
                return FetchResult(
                    url=url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error="Redirect to out-of-scope host rejected by acquisition policy",
                )
            if resp is _REDIRECT_LOOP_EXCEEDED:
                return FetchResult(
                    url=url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error="Redirect limit exceeded (possible redirect loop)",
                )
            if resp is _REDIRECT_MALFORMED_LOCATION:
                return FetchResult(
                    url=url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error="Malformed redirect Location URL (invalid IPv6 or other parse error)",
                )
        elif config is None:
            try:
                resp = self._request_with_legacy_400_retry(
                    url, timeout, egress_policy=egress_policy
                )
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
                # #1295: re-check egress policy before each retry attempt dispatch
                if attempt_index > 0 and egress_policy is not None and not egress_policy.is_authorized(url):
                    return FetchResult(
                        url=url,
                        ok=False,
                        provider=self.name,
                        fetched_at=now,
                        error="Egress blocked: destination URL rejected by public egress policy",
                    )
                try:
                    resp = self._request_once(url, timeout, self.headers)
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

    def _fetch_compatibility(
        self,
        url: str,
        timeout: tuple[float, float] | float | int,
        now: str,
        legacy_transport: bool = False,
        acquisition_policy: Any = None,
        egress_policy: Any = None,
        **kwargs: Any,
    ) -> FetchResult:
        """Opt-in compatibility path (``compatibility_mode=True``).

        Honors the caller's ``headers`` verbatim (no default merge, ``{}`` sent
        as-is) and performs a single GET with NO legacy 400 retry and NO
        FetchConfig status-code retries. HTTP 4xx/5xx are returned as
        ``ok=False`` / ``error="HTTP <status>"`` while still preserving the
        body (html/text), url, status_code and content_type.

        The additional ``legacy_transport=True`` opt-in (crawler/mapper
        migration only) keeps the caller's scalar ``timeout`` verbatim instead
        of the split (connect, read) tuple, mirroring the original direct
        ``requests.get`` fallback. It does not change retries, encoding, or the
        error-shape behavior. It is only effective when ``compatibility_mode``
        is also set.
        """
        ep = egress_policy if egress_policy is not None else self.egress_policy
        if ep is not None and not ep.is_authorized(url):
            return FetchResult(
                url=url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                error="Egress blocked: destination URL rejected by public egress policy",
            )

        headers = kwargs.get("headers", {})
        if acquisition_policy is not None or ep is not None:
            # #1294: same pre-dispatch redirect host containment on the
            # compatibility path (legacy crawler/mapper transport).
            resp = self._fetch_with_scope(
                url,
                timeout,
                headers,
                acquisition_policy,
                egress_policy=ep,
            )
            if resp is _EGRESS_POLICY_BLOCKED:
                return FetchResult(
                    url=url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error="Redirect to prohibited destination rejected by public egress policy",
                )
            if resp is _REDIRECT_SCOPE_BLOCKED:
                return FetchResult(
                    url=url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error="Redirect to out-of-scope host rejected by acquisition policy",
                )
            if resp is _REDIRECT_LOOP_EXCEEDED:
                return FetchResult(
                    url=url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error="Redirect limit exceeded (possible redirect loop)",
                )
            if resp is _REDIRECT_MALFORMED_LOCATION:
                return FetchResult(
                    url=url,
                    ok=False,
                    provider=self.name,
                    fetched_at=now,
                    error="Malformed redirect Location URL (invalid IPv6 or other parse error)",
                )
        else:
            try:
                resp = self._request_once(url, timeout, headers)
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

        if status_code >= 400:
            # Before handing the error body back, normalize ISO-8859-1 responses
            # to their apparent encoding (same rule as the success path) so the
            # preserved html/text are correctly decoded for the caller.
            if legacy_transport and resp.encoding == "ISO-8859-1":
                resp.encoding = resp.apparent_encoding
            return FetchResult(
                url=final_url,
                ok=False,
                provider=self.name,
                fetched_at=now,
                status_code=status_code,
                content_type=content_type,
                html=resp.text,
                text=resp.text,
                error=f"HTTP {status_code}",
            )

        # Success: parse HTML. Non-HTML keeps text only (matches base path).
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

        if resp.encoding == "ISO-8859-1":
            resp.encoding = resp.apparent_encoding

        try:
            soup = BeautifulSoup(resp.text, "html.parser")

            title = ""
            title_tag = soup.title
            if title_tag:
                title = title_tag.get_text().strip()

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

            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            raw_text = soup.get_text(separator="\n")
            text_lines = [line.strip() for line in raw_text.splitlines()]
            clean_text = "\n".join(line for line in text_lines if line)

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
