"""Fact value normalization for official-source extraction results."""

from __future__ import annotations

import re

from .models import FactKind, FactValue

_WS_RE = re.compile(r"\s+")
_HONORIFIC_RE = re.compile(r"(구청장|님|氏|씨)$")

# Explicit placeholders — never treat as a real current fact.
_PLACEHOLDERS = frozenset(
    {
        "-",
        "—",
        "–",
        "n/a",
        "na",
        "tbd",
        "todo",
        "null",
        "none",
        "미정",
        "없음",
        "준비중",
        "placeholder",
        "unknown",
        "테스트",
        "sample",
        "example",
    }
)


def normalize_whitespace(value: str) -> str:
    return _WS_RE.sub(" ", (value or "").strip())


def is_placeholder(value: str) -> bool:
    return normalize_whitespace(value).lower() in _PLACEHOLDERS


def normalize_fact_value(kind: FactKind, raw_value: str) -> FactValue | None:
    """Normalize a raw extracted string into a ``FactValue``.

    Returns ``None`` for empty or placeholder values. Does not invent values.
    """
    raw = normalize_whitespace(raw_value)
    if not raw or is_placeholder(raw):
        return None

    if kind in {
        FactKind.CURRENT_MAYOR,
        FactKind.DISTRICT_EXECUTIVE,
        FactKind.REGIONAL_EXECUTIVE,
    }:
        value = _HONORIFIC_RE.sub("", raw).strip()
        value = re.sub(r"(시장|통합특별시장|특별시장)$", "", value).strip()
        value = normalize_whitespace(value)
        if not value or is_placeholder(value):
            return None
        return FactValue(kind=kind, value=value, raw_value=raw)

    if kind in {
        FactKind.JURISDICTION_NAME,
        FactKind.AGENCY_NAME,
        FactKind.ADMINISTRATIVE_STATUS,
    }:
        value = normalize_whitespace(raw)
        for suffix in (" 홈페이지", " 공식 홈페이지", " 누리집"):
            if value.endswith(suffix):
                value = value[: -len(suffix)].strip()
        if not value or is_placeholder(value):
            return None
        return FactValue(kind=kind, value=value, raw_value=raw)

    # Other expanded kinds: non-empty non-placeholder string only (no invention).
    if kind in {
        FactKind.OFFICE_HOURS,
        FactKind.CONTACT_INFORMATION,
        FactKind.FEE,
        FactKind.APPLICATION_PERIOD,
        FactKind.CURRENT_NOTICE,
        FactKind.CURRENT_POLICY,
        FactKind.CURRENT_LAW,
        FactKind.CURRENT_EVENT,
        FactKind.GENERAL_CURRENT_INFORMATION,
    }:
        value = normalize_whitespace(raw)
        if not value or is_placeholder(value):
            return None
        return FactValue(kind=kind, value=value, raw_value=raw)

    return None


__all__ = [
    "is_placeholder",
    "normalize_fact_value",
    "normalize_whitespace",
]
