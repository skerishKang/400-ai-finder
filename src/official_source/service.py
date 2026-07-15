"""Orchestration for official-source freshness retrieval (fail-closed).

Wires classification → policy → transport → redirect/origin checks →
extraction → freshness assessment into a single structured result.

Never invents civic facts. Never performs live network by default.
"""

from __future__ import annotations

from .classification import classify_question
from .extraction import (
    AmbiguousValueError,
    ExtractionError,
    FactAbsentError,
    MalformedHtmlError,
    resolve_single_fact,
)
from .freshness import InvalidTimestampError, assess_freshness
from .models import (
    ErrorCode,
    FactKind,
    FreshnessStatus,
    OfficialSourceRequest,
    OfficialSourceResult,
    SourceMetadata,
    successful,
    unsuccessful,
)
from .policy import (
    canonicalize_official_url,
    get_policy_for_fact,
    is_official_host,
    is_url_allowlisted,
)
from .transport import MockOfficialSourceTransport, OfficialSourceTransport, TransportResponse


class OfficialSourceFreshnessService:
    """Phase-1 official-source freshness service.

    Args:
        transport: Injection point for retrieval. Defaults to an empty mock
            transport that fails closed (no network).
    """

    def __init__(self, transport: OfficialSourceTransport | None = None) -> None:
        self._transport: OfficialSourceTransport = (
            transport if transport is not None else MockOfficialSourceTransport()
        )

    @property
    def transport_name(self) -> str:
        return self._transport.name

    def retrieve(self, question: str, *, evaluated_at: str | None = None) -> OfficialSourceResult:
        """Classify and retrieve a time-sensitive official fact for ``question``."""
        request = OfficialSourceRequest(question=question, evaluated_at=evaluated_at)
        return self.retrieve_request(request)

    def retrieve_request(self, request: OfficialSourceRequest) -> OfficialSourceResult:
        try:
            return self._retrieve_request(request)
        except Exception as exc:  # noqa: BLE001 — last-resort fail-closed
            return unsuccessful(
                error_code=ErrorCode.INTERNAL_ERROR,
                error_message=f"internal error: {exc}",
                fact_kind=request.fact_kind,
            )

    def _retrieve_request(self, request: OfficialSourceRequest) -> OfficialSourceResult:
        fact_kind = request.fact_kind
        if fact_kind is None:
            classification = classify_question(request.question)
            if not classification.supported or classification.fact_kind is None:
                return unsuccessful(
                    error_code=ErrorCode.UNSUPPORTED_QUESTION,
                    error_message=(
                        "question is not a supported time-sensitive official-source fact"
                    ),
                )
            fact_kind = classification.fact_kind

        policy = get_policy_for_fact(fact_kind)
        if not is_url_allowlisted(policy.url, fact_kind):
            # Policy misconfiguration guard — still fail-closed.
            return unsuccessful(
                error_code=ErrorCode.NON_ALLOWLISTED_URL,
                error_message="policy URL is not on the official allowlist",
                fact_kind=fact_kind,
            )

        response = self._transport.fetch(policy.url)
        return self._interpret_transport(
            fact_kind=fact_kind,
            policy_url=policy.url,
            policy_title=policy.title,
            max_age_seconds=policy.max_age_seconds,
            fact_marker=policy.fact_marker,
            response=response,
            evaluated_at=request.evaluated_at,
        )

    def _interpret_transport(
        self,
        *,
        fact_kind: FactKind,
        policy_url: str,
        policy_title: str,
        max_age_seconds: int,
        fact_marker: str,
        response: TransportResponse,
        evaluated_at: str | None,
    ) -> OfficialSourceResult:
        if response.timed_out:
            return unsuccessful(
                error_code=ErrorCode.TRANSPORT_TIMEOUT,
                error_message=response.error or "official source transport timed out",
                fact_kind=fact_kind,
            )

        if not response.ok:
            # Distinguish missing source configuration vs generic transport fail.
            if response.error in {
                "mock_transport_no_response_configured",
                "missing_source",
            } or response.status_code == 404:
                return unsuccessful(
                    error_code=ErrorCode.MISSING_SOURCE,
                    error_message=response.error or "official source missing",
                    fact_kind=fact_kind,
                )
            return unsuccessful(
                error_code=ErrorCode.TRANSPORT_FAILURE,
                error_message=response.error or "official source transport failure",
                fact_kind=fact_kind,
            )

        final_url = response.final_url or response.requested_url or policy_url
        origin_error = self._check_origin_and_redirect(
            policy_url=policy_url,
            final_url=final_url,
            redirected=response.redirected,
            fact_kind=fact_kind,
        )
        if origin_error is not None:
            return origin_error

        if not is_url_allowlisted(final_url, fact_kind) and not is_url_allowlisted(
            response.requested_url, fact_kind
        ):
            return unsuccessful(
                error_code=ErrorCode.NON_ALLOWLISTED_URL,
                error_message="retrieved URL is not on the official allowlist",
                fact_kind=fact_kind,
                source=SourceMetadata(
                    url=policy_url,
                    title=response.title or policy_title,
                    retrieved_at=response.retrieved_at or "",
                    final_url=final_url,
                    content_type=response.content_type,
                ),
            )

        # Freshness / timestamp first so invalid clocks never yield a fact.
        if not response.retrieved_at:
            return unsuccessful(
                error_code=ErrorCode.INVALID_TIMESTAMP,
                error_message="retrieved_at timestamp is missing",
                fact_kind=fact_kind,
                source=SourceMetadata(
                    url=policy_url,
                    title=response.title or policy_title,
                    retrieved_at="",
                    final_url=final_url,
                    content_type=response.content_type,
                ),
            )

        try:
            freshness = assess_freshness(
                retrieved_at=response.retrieved_at,
                max_age_seconds=max_age_seconds,
                evaluated_at=evaluated_at,
            )
        except InvalidTimestampError as exc:
            return unsuccessful(
                error_code=ErrorCode.INVALID_TIMESTAMP,
                error_message=str(exc),
                fact_kind=fact_kind,
                source=SourceMetadata(
                    url=policy_url,
                    title=response.title or policy_title,
                    retrieved_at=response.retrieved_at,
                    final_url=final_url,
                    content_type=response.content_type,
                ),
            )

        source = SourceMetadata(
            url=policy_url,
            title=response.title or policy_title,
            retrieved_at=freshness.retrieved_at,
            final_url=final_url,
            content_type=response.content_type,
        )

        if freshness.status is FreshnessStatus.STALE:
            return unsuccessful(
                error_code=ErrorCode.STALE_RETRIEVAL,
                error_message=(
                    f"official source retrieval is stale "
                    f"(age_seconds={freshness.age_seconds}, "
                    f"max_age_seconds={max_age_seconds})"
                ),
                fact_kind=fact_kind,
                source=source,
                freshness_status=FreshnessStatus.STALE,
                max_age_seconds=max_age_seconds,
                age_seconds=freshness.age_seconds,
            )

        try:
            fact, extracted_title = resolve_single_fact(
                response.html,
                fact_kind=fact_kind,
                fact_marker=fact_marker,
            )
        except MalformedHtmlError as exc:
            return unsuccessful(
                error_code=ErrorCode.MALFORMED_HTML,
                error_message=exc.message,
                fact_kind=fact_kind,
                source=source,
                freshness_status=freshness.status,
                max_age_seconds=max_age_seconds,
                age_seconds=freshness.age_seconds,
            )
        except FactAbsentError as exc:
            return unsuccessful(
                error_code=ErrorCode.FACT_ABSENT,
                error_message=exc.message,
                fact_kind=fact_kind,
                source=source,
                freshness_status=freshness.status,
                max_age_seconds=max_age_seconds,
                age_seconds=freshness.age_seconds,
            )
        except AmbiguousValueError as exc:
            return unsuccessful(
                error_code=ErrorCode.AMBIGUOUS_VALUE,
                error_message=exc.message,
                fact_kind=fact_kind,
                source=source,
                freshness_status=freshness.status,
                max_age_seconds=max_age_seconds,
                age_seconds=freshness.age_seconds,
            )
        except ExtractionError as exc:
            return unsuccessful(
                error_code=ErrorCode.INTERNAL_ERROR,
                error_message=exc.message,
                fact_kind=fact_kind,
                source=source,
                freshness_status=freshness.status,
                max_age_seconds=max_age_seconds,
                age_seconds=freshness.age_seconds,
            )

        if extracted_title and not response.title:
            source = SourceMetadata(
                url=source.url,
                title=extracted_title,
                retrieved_at=source.retrieved_at,
                final_url=source.final_url,
                content_type=source.content_type,
            )

        return successful(
            fact=fact,
            source=source,
            freshness_status=freshness.status,
            max_age_seconds=max_age_seconds,
            age_seconds=freshness.age_seconds,
        )

    def _check_origin_and_redirect(
        self,
        *,
        policy_url: str,
        final_url: str,
        redirected: bool,
        fact_kind: FactKind,
    ) -> OfficialSourceResult | None:
        if not is_official_host(final_url):
            return unsuccessful(
                error_code=ErrorCode.EXTERNAL_ORIGIN,
                error_message=f"final URL is outside official origin: {final_url}",
                fact_kind=fact_kind,
                source=SourceMetadata(
                    url=policy_url,
                    title="",
                    retrieved_at="",
                    final_url=final_url,
                ),
            )

        policy_canon = canonicalize_official_url(policy_url)
        final_canon = canonicalize_official_url(final_url)
        if redirected and policy_canon != final_canon:
            # Redirect that leaves the exact allowlisted resource.
            if not is_url_allowlisted(final_url, fact_kind):
                return unsuccessful(
                    error_code=ErrorCode.UNEXPECTED_REDIRECT,
                    error_message=(
                        f"redirect left allowlisted resource: "
                        f"{policy_url} -> {final_url}"
                    ),
                    fact_kind=fact_kind,
                    source=SourceMetadata(
                        url=policy_url,
                        title="",
                        retrieved_at="",
                        final_url=final_url,
                    ),
                )
        return None


__all__ = [
    "OfficialSourceFreshnessService",
]
