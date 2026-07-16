"""Surface-form aliases for current civic entities (no permanent fact values).

Maps *phrases residents may type* onto abstract entity keys used for search
routing. Never hard-codes office-holder names as product truth.

Historical questions (explicit past dates / "당시" / year markers) do not force
current-entity alias substitution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import FactKind, TemporalMode, TemporalPrecision

_WS_RE = re.compile(r"\s+")

_HISTORICAL_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(19|20)\d{2}\s*년"),
    re.compile(r"\b(19|20)\d{2}[./-]\d{1,2}([./-]\d{1,2})?"),
    re.compile(r"당시"),
    re.compile(r"예전"),
    re.compile(r"과거"),
    re.compile(r"이전\s*(시장|구청장|명칭|이름)"),
    re.compile(r"전에\s*(시장|구청장)"),
    re.compile(r"as\s+of\s+(19|20)\d{2}", re.I),
    re.compile(r"in\s+(19|20)\d{2}", re.I),
)

_YEAR_ONLY_RE = re.compile(r"(19|20)\d{2}\s*년")
_FULL_DATE_RE = re.compile(r"((19|20)\d{2})[./-](\d{1,2})[./-](\d{1,2})")
_YEAR_MONTH_RE = re.compile(r"((19|20)\d{2})[./-](\d{1,2})(?![./-]\d)")


@dataclass(frozen=True)
class AliasResolution:
    historical: bool
    as_of_date: str | None
    as_of_year: int | None
    temporal_precision: TemporalPrecision
    temporal_mode: TemporalMode
    matched_aliases: tuple[str, ...]
    entity_keys: tuple[str, ...]
    preferred_fact_kind: FactKind | None
    force_current_entity: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "historical": self.historical,
            "as_of_date": self.as_of_date,
            "as_of_year": self.as_of_year,
            "temporal_precision": self.temporal_precision.value,
            "temporal_mode": self.temporal_mode.value,
            "matched_aliases": list(self.matched_aliases),
            "entity_keys": list(self.entity_keys),
            "preferred_fact_kind": (
                self.preferred_fact_kind.value if self.preferred_fact_kind else None
            ),
            "force_current_entity": self.force_current_entity,
        }


_ALIAS_TABLE: tuple[tuple[str, str, FactKind], ...] = (
    ("전남광주통합특별시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("전남광주특별시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("광주광역시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("통합시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("특별시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("광주시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("광주 시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("전남광주통합특별시", "regional_jurisdiction", FactKind.JURISDICTION_NAME),
    ("광주광역시", "regional_jurisdiction", FactKind.JURISDICTION_NAME),
    ("광주특별시", "regional_jurisdiction", FactKind.JURISDICTION_NAME),
    ("전라남도", "regional_jurisdiction_legacy", FactKind.ADMINISTRATIVE_STATUS),
    ("전남광주통합특별시 북구", "district_jurisdiction", FactKind.JURISDICTION_NAME),
    ("광주광역시 북구", "district_jurisdiction", FactKind.JURISDICTION_NAME),
    ("광주 북구", "district_jurisdiction", FactKind.JURISDICTION_NAME),
    ("북구청장", "district_executive_office", FactKind.DISTRICT_EXECUTIVE),
    ("북구 구청장", "district_executive_office", FactKind.DISTRICT_EXECUTIVE),
    ("북구청", "district_agency", FactKind.AGENCY_NAME),
)


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text.strip().lower())


def detect_historical_reference(
    question: str,
) -> tuple[bool, str | None, int | None, TemporalPrecision]:
    """Return (is_historical, as_of_date, as_of_year, precision).

    Year-only questions set as_of_year without inventing a calendar day claim.
    ``as_of_date`` may be a year-label like ``2020`` (not ``2020-01-01``).
    """
    if not isinstance(question, str) or not question.strip():
        return False, None, None, TemporalPrecision.UNSPECIFIED
    normalized = _normalize(question)

    m_full = _FULL_DATE_RE.search(normalized)
    if m_full:
        y, mo, d = int(m_full.group(1)), int(m_full.group(3)), int(m_full.group(4))
        return True, f"{y:04d}-{mo:02d}-{d:02d}", y, TemporalPrecision.DATE

    # Year-only (preferred over year-month for "2020년")
    m_year = _YEAR_ONLY_RE.search(normalized)
    if m_year:
        y = int(re.search(r"(19|20)\d{2}", m_year.group(0)).group(0))  # type: ignore[union-attr]
        return True, str(y), y, TemporalPrecision.YEAR

    m_ym = _YEAR_MONTH_RE.search(normalized)
    if m_ym:
        y, mo = int(m_ym.group(1)), int(m_ym.group(3))
        return True, f"{y:04d}-{mo:02d}", y, TemporalPrecision.DATE

    for pattern in _HISTORICAL_MARKERS:
        m = pattern.search(normalized)
        if m:
            year_m = re.search(r"(19|20)\d{2}", m.group(0))
            if year_m:
                y = int(year_m.group(0))
                return True, str(y), y, TemporalPrecision.YEAR
            return True, None, None, TemporalPrecision.UNSPECIFIED
    return False, None, None, TemporalPrecision.UNSPECIFIED


def resolve_aliases(question: str) -> AliasResolution:
    if not isinstance(question, str):
        return AliasResolution(
            historical=False,
            as_of_date=None,
            as_of_year=None,
            temporal_precision=TemporalPrecision.UNSPECIFIED,
            temporal_mode=TemporalMode.CURRENT,
            matched_aliases=(),
            entity_keys=(),
            preferred_fact_kind=None,
            force_current_entity=False,
        )
    historical, as_of_date, as_of_year, precision = detect_historical_reference(question)
    normalized = _normalize(question)
    matched: list[str] = []
    entities: list[str] = []
    preferred: FactKind | None = None
    for surface, entity_key, fact_kind in _ALIAS_TABLE:
        surface_n = _normalize(surface)
        if surface_n and surface_n in normalized:
            matched.append(surface)
            if entity_key not in entities:
                entities.append(entity_key)
            if preferred is None:
                preferred = fact_kind

    force_current = bool(matched) and not historical
    return AliasResolution(
        historical=historical,
        as_of_date=as_of_date,
        as_of_year=as_of_year,
        temporal_precision=precision if historical else TemporalPrecision.UNSPECIFIED,
        temporal_mode=TemporalMode.HISTORICAL if historical else TemporalMode.CURRENT,
        matched_aliases=tuple(matched),
        entity_keys=tuple(entities),
        preferred_fact_kind=preferred,
        force_current_entity=force_current,
    )


def alias_table_for_tests() -> tuple[tuple[str, str, str], ...]:
    return tuple((s, e, k.value) for s, e, k in _ALIAS_TABLE)


__all__ = [
    "AliasResolution",
    "alias_table_for_tests",
    "detect_historical_reference",
    "resolve_aliases",
]
