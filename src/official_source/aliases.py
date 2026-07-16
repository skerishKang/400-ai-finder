"""Surface-form aliases for current civic entities (no permanent fact values).

Maps *phrases residents may type* onto abstract entity keys used for search
routing. Never hard-codes the current mayor name, city name, or office holder
as product truth — only alias → entity_kind mapping for *current* questions.

Historical questions (explicit past dates / "당시" / year before a threshold)
do not force current-entity alias substitution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import FactKind

_WS_RE = re.compile(r"\s+")

# Explicit past markers — do not rewrite aliases to present entities.
_HISTORICAL_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(19|20)\d{2}\s*년"),
    re.compile(r"\b(19|20)\d{2}[./-]\d{1,2}"),
    re.compile(r"당시"),
    re.compile(r"예전"),
    re.compile(r"과거"),
    re.compile(r"이전\s*(시장|구청장|명칭|이름)"),
    re.compile(r"전에\s*(시장|구청장)"),
    re.compile(r"as\s+of\s+(19|20)\d{2}", re.I),
    re.compile(r"in\s+(19|20)\d{2}", re.I),
)


@dataclass(frozen=True)
class AliasResolution:
    """Alias resolution outcome (routing aid only — not a fact claim)."""

    historical: bool
    as_of_date: str | None
    matched_aliases: tuple[str, ...]
    entity_keys: tuple[str, ...]
    preferred_fact_kind: FactKind | None
    force_current_entity: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "historical": self.historical,
            "as_of_date": self.as_of_date,
            "matched_aliases": list(self.matched_aliases),
            "entity_keys": list(self.entity_keys),
            "preferred_fact_kind": (
                self.preferred_fact_kind.value if self.preferred_fact_kind else None
            ),
            "force_current_entity": self.force_current_entity,
        }


# Surface phrase → abstract entity key (NOT the office-holder name).
# Order: longer / more specific phrases first when matching.
_ALIAS_TABLE: tuple[tuple[str, str, FactKind], ...] = (
    # Regional executive (metropolitan / special city mayor seat — abstract)
    ("전남광주통합특별시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("전남광주특별시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("광주광역시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("통합시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("특별시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("광주시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    ("광주 시장", "regional_executive_office", FactKind.REGIONAL_EXECUTIVE),
    # Regional jurisdiction names (abstract entity, not fixed string value)
    ("전남광주통합특별시", "regional_jurisdiction", FactKind.JURISDICTION_NAME),
    ("광주광역시", "regional_jurisdiction", FactKind.JURISDICTION_NAME),
    ("광주특별시", "regional_jurisdiction", FactKind.JURISDICTION_NAME),
    ("전라남도", "regional_jurisdiction_legacy", FactKind.ADMINISTRATIVE_STATUS),
    # District
    ("전남광주통합특별시 북구", "district_jurisdiction", FactKind.JURISDICTION_NAME),
    ("광주광역시 북구", "district_jurisdiction", FactKind.JURISDICTION_NAME),
    ("광주 북구", "district_jurisdiction", FactKind.JURISDICTION_NAME),
    ("북구청장", "district_executive_office", FactKind.DISTRICT_EXECUTIVE),
    ("북구 구청장", "district_executive_office", FactKind.DISTRICT_EXECUTIVE),
    ("북구청", "district_agency", FactKind.AGENCY_NAME),
)


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text.strip().lower())


def detect_historical_reference(question: str) -> tuple[bool, str | None]:
    """Return (is_historical, as_of_date_hint)."""
    if not isinstance(question, str) or not question.strip():
        return False, None
    normalized = _normalize(question)
    for pattern in _HISTORICAL_MARKERS:
        m = pattern.search(normalized)
        if m:
            # Best-effort year extraction
            year_m = re.search(r"(19|20)\d{2}", m.group(0))
            as_of = f"{year_m.group(0)}-01-01" if year_m else None
            return True, as_of
    return False, None


def resolve_aliases(question: str) -> AliasResolution:
    """Resolve surface aliases without asserting current office-holder values."""
    if not isinstance(question, str):
        return AliasResolution(
            historical=False,
            as_of_date=None,
            matched_aliases=(),
            entity_keys=(),
            preferred_fact_kind=None,
            force_current_entity=False,
        )
    historical, as_of = detect_historical_reference(question)
    normalized = _normalize(question)
    # Match against lowercased surface forms
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

    # Current-entity forcing only when not historical.
    force_current = bool(matched) and not historical
    return AliasResolution(
        historical=historical,
        as_of_date=as_of,
        matched_aliases=tuple(matched),
        entity_keys=tuple(entities),
        preferred_fact_kind=preferred if force_current else (
            preferred if historical else preferred
        ),
        force_current_entity=force_current,
    )


def alias_table_for_tests() -> tuple[tuple[str, str, str], ...]:
    """Expose surface → entity_key → fact_kind for contract tests."""
    return tuple((s, e, k.value) for s, e, k in _ALIAS_TABLE)


__all__ = [
    "AliasResolution",
    "alias_table_for_tests",
    "detect_historical_reference",
    "resolve_aliases",
]
