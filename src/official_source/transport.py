"""Transport interface and mock provider for official-source retrieval.

Phase 1 ships only a mock transport. Construction and default use perform
no network I/O. A live transport is intentionally not provided here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class TransportResponse:
    """Raw transport outcome for a single official-source request URL."""

    ok: bool
    requested_url: str
    final_url: str = ""
    status_code: int = 0
    title: str = ""
    html: str = ""
    content_type: str = "text/html"
    retrieved_at: str = ""
    error: str = ""
    timed_out: bool = False
    redirected: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "title": self.title,
            "html": self.html,
            "content_type": self.content_type,
            "retrieved_at": self.retrieved_at,
            "error": self.error,
            "timed_out": self.timed_out,
            "redirected": self.redirected,
            "extra": dict(self.extra),
        }


class OfficialSourceTransport(ABC):
    """Abstract transport. Implementations must not run network on import."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def fetch(self, url: str) -> TransportResponse:
        """Fetch ``url`` and return a transport response (no exceptions for I/O)."""
        ...


class MockOfficialSourceTransport(OfficialSourceTransport):
    """In-memory mock transport for deterministic unit tests.

    Configure per-URL responses via ``responses``. Missing URLs fail closed
    with ``ok=False`` (MISSING-style transport failure), never invent content.
    """

    def __init__(
        self,
        responses: Mapping[str, TransportResponse] | None = None,
        *,
        default_failure: TransportResponse | None = None,
    ) -> None:
        self._responses: dict[str, TransportResponse] = dict(responses or {})
        self._default_failure = default_failure
        self._call_log: list[str] = []

    @property
    def name(self) -> str:
        return "mock_official_source"

    @property
    def call_log(self) -> tuple[str, ...]:
        return tuple(self._call_log)

    def set_response(self, url: str, response: TransportResponse) -> None:
        self._responses[url] = response

    def fetch(self, url: str) -> TransportResponse:
        self._call_log.append(url)
        if url in self._responses:
            return self._responses[url]
        if self._default_failure is not None:
            return TransportResponse(
                ok=self._default_failure.ok,
                requested_url=url,
                final_url=self._default_failure.final_url or url,
                status_code=self._default_failure.status_code,
                title=self._default_failure.title,
                html=self._default_failure.html,
                content_type=self._default_failure.content_type,
                retrieved_at=self._default_failure.retrieved_at,
                error=self._default_failure.error or "mock_default_failure",
                timed_out=self._default_failure.timed_out,
                redirected=self._default_failure.redirected,
                extra=self._default_failure.extra,
            )
        return TransportResponse(
            ok=False,
            requested_url=url,
            final_url=url,
            status_code=0,
            error="mock_transport_no_response_configured",
            retrieved_at="",
        )


class LiveTransportNotAuthorized(OfficialSourceTransport):
    """Explicit fail-closed stand-in: live retrieval is not authorized in Phase 1."""

    @property
    def name(self) -> str:
        return "live_not_authorized"

    def fetch(self, url: str) -> TransportResponse:
        return TransportResponse(
            ok=False,
            requested_url=url,
            final_url=url,
            status_code=0,
            error="live_official_source_retrieval_not_authorized_in_phase_1",
            retrieved_at="",
        )


__all__ = [
    "LiveTransportNotAuthorized",
    "MockOfficialSourceTransport",
    "OfficialSourceTransport",
    "TransportResponse",
]
