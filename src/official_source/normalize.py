"""Fact value normalization for official-source extraction results."""

from __future__ import annotations

import re

from .models import FactKind, FactValue

_WS_RE = re.compile(r"\s+")
_HONORIFIC_RE = re.compile(r"(구청장|님|氏|씨)$")


def normalize_whitespace(value: str) -> str:
    return _WS_RE.sub(" ", (value or "").strip())


def normalize_fact_value(kind: FactKind, raw_value: str) -> FactValue | None:
    """Normalize a raw extracted string into a ``FactValue``.

    Returns ``None`` when the raw value is empty after normalization.
    Does not invent values.
    """
    raw = normalize_whitespace(raw_value)
    if not raw:
        return None

    if kind is FactKind.CURRENT_MAYOR:
        # Strip trailing honorifics for a stable civic fact value.
        value = _HONORIFIC_RE.sub("", raw).strip()
        value = normalize_whitespace(value)
        if not value:
            return None
        return FactValue(kind=kind, value=value, raw_value=raw)

    if kind is FactKind.JURISDICTION_NAME:
        value = normalize_whitespace(raw)
        # Collapse common "official site" suffixes that are not the name itself.
        for suffix in (" 홈페이지", " 공식 홈페이지", " 누리집"):
            if value.endswith(suffix):
                value = value[: -len(suffix)].strip()
        if not value:
            return None
        return FactValue(kind=kind, value=value, raw_value=raw)

    return None


__all__ = [
    "normalize_fact_value",
    "normalize_whitespace",
]
