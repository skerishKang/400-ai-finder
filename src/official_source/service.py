"""Orchestration for official-source freshness retrieval (fail-closed).

Dependency direction:
  classification → policy → transport → origin checks → content gates →
  extraction → freshness → structured result

Never invents civic facts. Default transport is mock (no network).
"""

from __future__ import annotations

from typing import Callable
from datetime import datetime

from .classification import classify_question
from .extraction import (
    AmbiguousValueError,
    ExtractionError,
    FactAbsentError,
    MalformedHtmlError,
    SourceIdentityMismatchError,
    resolve_single_fact,
)
from .freshness import InvalidTimestampError, assess_freshness
from .models import (
    EXTRACTOR_ID,
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
    assess_url_allowlist,
    canonicalize_official_url,
    get_policy_for_fact,
    is_official_host,
    is_url_allowlisted,
)
from .transport import (
    MockOfficialSourceTransport,
    OfficialSourceTransport,
    TransportException,
    TransportResponse,
)

Clock = Callable[[], datetime]

_HTML_CONTENT_TYPE_PREFIXES = ("text/html", "application/xhtml+xml")


class OfficialSourceFreshnessService:
    """Phase-1 official-source freshness service."""

    def __init__(
        self,
        transport: OfficialSourceTransport | None = None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._transport: OfficialSourceTransport = (
            transport if transport is not None else MockOfficialSourceTransport()
        )
        self._clock = clock

    @property
    def transport_name(self) -> str:
        return self._transport.name

    def retrieve(
        self,
        question: str,
        *,
        evaluated_at: str | None = None,
    ) -> OfficialSourceResult:
        request = OfficialSourceRequest(question=question, evaluated_at=evaluated_at)
        return self.retrieve_request(request)

    def retrieve_request(self, request: OfficialSourceRequest) -> OfficialSourceResult:
        try:
            return self._retrieve_request(request)
        except TransportException:
            return unsuccessful(
                failure_code=ErrorCode.TRANSPORT_ERROR,
                fact_kind=request.fact_kind,
            )
        except Exception:  # noqa: BLE001 — last-resort fail-closed
            return unsuccessful(
                failure_code=ErrorCode.INTERNAL_ERROR,
                fact_kind=request.fact_kind,
            )

    def _retrieve_request(self, request: OfficialSourceRequest) -> OfficialSourceResult:
        if request.question is None or (
            isinstance(request.question, str) and not request.question.strip()
            and request.fact_kind is None
        ):
            # Empty question without explicit fact_kind.
            if request.fact_kind is None:
                classification = classify_question(request.question)
                return unsuccessful(
                    failure_code=classification.failure_code
                    or ErrorCode.INVALID_REQUEST,
                    fact_kind=None,
                )

        fact_kind = request.fact_kind
        if fact_kind is None:
            classification = classify_question(request.question)
            if not classification.supported or classification.fact_kind is None:
                return unsuccessful(
                    failure_code=classification.failure_code
                    or ErrorCode.UNSUPPORTED_QUESTION,
                )
            fact_kind = classification.fact_kind

        policy = get_policy_for_fact(fact_kind)
        assessment = assess_url_allowlist(policy.url, fact_kind)
        if not assessment["allowed"]:
            return unsuccessful(
                failure_code=ErrorCode.SOURCE_NOT_ALLOWLISTED,
                fact_kind=fact_kind,
            )

        transport_request = OfficialSourceRequest(
            question=request.question,
            fact_kind=fact_kind,
            target_url=policy.url,
            evaluated_at=request.evaluated_at,
        )
        response = self._transport.fetch(transport_request)
        return self._interpret_transport(
            fact_kind=fact_kind,
            policy_url=policy.url,
            policy_title=policy.title,
            expected_title_tokens=policy.expected_title_tokens,
            max_age_seconds=policy.max_age_seconds,
            max_body_bytes=policy.max_body_bytes,
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
        expected_title_tokens: tuple[str, ...],
        max_age_seconds: int,
        max_body_bytes: int,
        fact_marker: str,
        response: TransportResponse,
        evaluated_at: str | None,
    ) -> OfficialSourceResult:
        if response.timed_out:
            return unsuccessful(
                failure_code=ErrorCode.TRANSPORT_TIMEOUT,
                fact_kind=fact_kind,
            )

        if not response.ok:
            if response.status_code >= 400:
                return unsuccessful(
                    failure_code=ErrorCode.HTTP_ERROR,
                    fact_kind=fact_kind,
                )
            return unsuccessful(
                failure_code=ErrorCode.TRANSPORT_ERROR,
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
                failure_code=ErrorCode.SOURCE_NOT_ALLOWLISTED,
                fact_kind=fact_kind,
                source=SourceMetadata(
                    url=policy_url,
                    title=response.title or policy_title,
                    retrieved_at=response.retrieved_at or "",
                    final_url=final_url,
                    content_type=response.content_type,
                ),
            )

        content_type = (response.content_type or "").split(";")[0].strip().lower()
        if content_type and not any(
            content_type == p or content_type.startswith(p)
            for p in _HTML_CONTENT_TYPE_PREFIXES
        ):
            return unsuccessful(
                failure_code=ErrorCode.INVALID_CONTENT_TYPE,
                fact_kind=fact_kind,
                source=SourceMetadata(
                    url=policy_url,
                    title=response.title or policy_title,
                    retrieved_at=response.retrieved_at or "",
                    final_url=final_url,
                    content_type=response.content_type,
                ),
            )

        body = response.html or ""
        if not body.strip():
            return unsuccessful(
                failure_code=ErrorCode.EMPTY_CONTENT,
                fact_kind=fact_kind,
                source=SourceMetadata(
                    url=policy_url,
                    title=response.title or policy_title,
                    retrieved_at=response.retrieved_at or "",
                    final_url=final_url,
                    content_type=response.content_type,
                ),
            )

        if len(body.encode("utf-8", errors="replace")) > max_body_bytes:
            return unsuccessful(
                failure_code=ErrorCode.MALFORMED_CONTENT,
                public_safe_message="공식 출처 본문이 허용 크기를 초과했습니다.",
                fact_kind=fact_kind,
                source=SourceMetadata(
                    url=policy_url,
                    title=response.title or policy_title,
                    retrieved_at=response.retrieved_at or "",
                    final_url=final_url,
                    content_type=response.content_type,
                ),
            )

        # Freshness before fact extraction so invalid clocks never yield a fact.
        try:
            freshness = assess_freshness(
                retrieved_at=response.retrieved_at,
                max_age_seconds=max_age_seconds,
                evaluated_at=evaluated_at,
                clock=self._clock,
            )
        except InvalidTimestampError:
            return unsuccessful(
                failure_code=ErrorCode.INVALID_TIMESTAMP,
                fact_kind=fact_kind,
                source=SourceMetadata(
                    url=policy_url,
                    title=response.title or policy_title,
                    retrieved_at=response.retrieved_at or "",
                    final_url=final_url,
                    content_type=response.content_type,
                ),
                freshness_status=FreshnessStatus.INVALID,
            )

        if freshness.status is FreshnessStatus.UNKNOWN:
            return unsuccessful(
                failure_code=ErrorCode.INVALID_TIMESTAMP,
                fact_kind=fact_kind,
                source=SourceMetadata(
                    url=policy_url,
                    title=response.title or policy_title,
                    retrieved_at="",
                    final_url=final_url,
                    content_type=response.content_type,
                ),
                freshness_status=FreshnessStatus.UNKNOWN,
                max_age_seconds=max_age_seconds,
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
                failure_code=ErrorCode.STALE_SOURCE,
                fact_kind=fact_kind,
                source=source,
                freshness_status=FreshnessStatus.STALE,
                max_age_seconds=max_age_seconds,
                age_seconds=freshness.age_seconds,
            )

        try:
            fact, extracted_title, _extractor = resolve_single_fact(
                body,
                fact_kind=fact_kind,
                fact_marker=fact_marker,
                expected_title_tokens=expected_title_tokens,
            )
        except MalformedHtmlError:
            return unsuccessful(
                failure_code=ErrorCode.MALFORMED_CONTENT,
                fact_kind=fact_kind,
                source=source,
                freshness_status=freshness.status,
                max_age_seconds=max_age_seconds,
                age_seconds=freshness.age_seconds,
            )
        except SourceIdentityMismatchError:
            return unsuccessful(
                failure_code=ErrorCode.SOURCE_IDENTITY_MISMATCH,
                fact_kind=fact_kind,
                source=source,
                freshness_status=freshness.status,
                max_age_seconds=max_age_seconds,
                age_seconds=freshness.age_seconds,
            )
        except FactAbsentError:
            return unsuccessful(
                failure_code=ErrorCode.FACT_NOT_FOUND,
                fact_kind=fact_kind,
                source=source,
                freshness_status=freshness.status,
                max_age_seconds=max_age_seconds,
                age_seconds=freshness.age_seconds,
            )
        except AmbiguousValueError:
            return unsuccessful(
                failure_code=ErrorCode.AMBIGUOUS_FACT,
                fact_kind=fact_kind,
                source=source,
                freshness_status=freshness.status,
                max_age_seconds=max_age_seconds,
                age_seconds=freshness.age_seconds,
            )
        except ExtractionError:
            return unsuccessful(
                failure_code=ErrorCode.INTERNAL_ERROR,
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
                failure_code=ErrorCode.EXTERNAL_REDIRECT
                if redirected
                else ErrorCode.SOURCE_NOT_ALLOWLISTED,
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
            if not is_url_allowlisted(final_url, fact_kind):
                return unsuccessful(
                    failure_code=ErrorCode.EXTERNAL_REDIRECT
                    if not is_official_host(final_url)
                    else ErrorCode.SOURCE_NOT_ALLOWLISTED,
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
    "EXTRACTOR_ID",
    "OfficialSourceFreshnessService",
]
