"""Closed-vocabulary ``answer_status`` taxonomy for demo/operator responses.

Stage #803: 박사님이 확정한 4-state enum. 각 상태는 ``answer_ok`` 와
직교하지 않으며, *왜* 답변이 (또는 fallback이) 생성되었는지를 표현한다.

Definitions (verbatim, 박사님 확정):

* ``answered_with_evidence`` — 근거 source 기반 답변 또는 허용된 직접
  응답 경로가 정상적으로 답변을 생성함. ``answer_ok=True`` 동반.
* ``fallback_no_match``    — source/snapshot 매칭이 없어 generic
  fallback이 반환됨. ``answer_ok=False`` 동반.
* ``fallback_unavailable`` — pipeline timeout으로 데이터 미수신,
  soft fallback 반환. ``answer_ok=False`` 동반. timeout 외 다른
  인프라 실패는 아래 ``error`` 로 분류한다.
* ``error``                — timeout 외 pipeline 예외 (예: connection_error,
  tls_error, http_error, blocked_or_forbidden, parse_error,
  unknown_fetch_error 등) 또는 처리 불가능 상태.
  ``answer_ok=False`` 동반.

분류는 ``pipeline_diagnostic.category`` 가 ``"timeout"`` 이면
``fallback_unavailable``, 그 외 closed-vocab category 또는 진단 부재면
``error`` 로 매핑한다. ``ok`` 필드는 transport/pipeline 성공 여부로
유지하며 ``answer_ok``/``answer_status`` 와 혼동하지 않는다.

This module is intentionally tiny: it owns the closed vocabulary and a
single sanity check. There is no I/O, no logging, no network access.
"""

from __future__ import annotations

from typing import Final

ANSWER_STATUSES: Final[tuple[str, ...]] = (
    "answered_with_evidence",
    "fallback_no_match",
    "fallback_unavailable",
    "error",
)


def is_valid_answer_status(value: object) -> bool:
    """Return True iff ``value`` is one of the closed-vocab statuses."""
    return isinstance(value, str) and value in ANSWER_STATUSES


def normalize_answer_status(value: object) -> str:
    """Return ``value`` if it is a valid status, else ``"error"``.

    Used as a defensive default for malformed snapshots / fixtures /
    legacy records so the conversation log never carries an unknown
    free-form string.
    """
    if is_valid_answer_status(value):
        # is_valid_answer_status already narrowed the type.
        return value  # type: ignore[return-value]
    return "error"


__all__ = [
    "ANSWER_STATUSES",
    "is_valid_answer_status",
    "normalize_answer_status",
]
