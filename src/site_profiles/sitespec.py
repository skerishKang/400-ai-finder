"""Dual-read canonical SiteSpec resolver (#1225-B).

Additive compatibility foundation: canonical site IDs and legacy aliases both
resolve to the same canonical SiteSpec loaded from
``configs/sites/*.sitespec.json``.

Design constraints (per #1225-B):
- canonical ID is the primary identity; ``legacy_ids`` are lookup aliases only.
- display labels and jurisdiction historical aliases are NOT site identifiers.
- deterministic + offline: sorted file enumeration, no network/provider calls.
- fail-closed: unknown, empty, malformed, or colliding identifiers raise;
  no silent default fallback; first-match-wins is prohibited.
- additive foundation only: no runtime migration, no registry change.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

CONFIGS_SITES_DIR = Path(__file__).resolve().parent.parent.parent / "configs" / "sites"

SITESPEC_GLOB = "*.sitespec.json"

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class SiteSpecError(Exception):
    """Base error for canonical SiteSpec loading and resolution."""


class SiteSpecLoadError(SiteSpecError):
    """The canonical SiteSpec set is malformed or self-inconsistent."""


class SiteSpecNotFoundError(SiteSpecError, KeyError):
    """An identifier does not resolve to any canonical SiteSpec."""


class JurisdictionResolutionError(SiteSpecError):
    """Date-aware jurisdiction selection failed (fail-closed).

    Raised by :func:`resolve_jurisdiction_at` when the jurisdiction timeline is
    malformed, ambiguous, gapped, or overlapping — or when ``as_of`` or any
    effective date is not a real calendar date. No silent fallback or
    first-match-wins behavior occurs.
    """


def iter_sitespec_paths(sites_dir: Path) -> list[Path]:
    """Return SiteSpec files in sorted (deterministic) order."""
    return sorted(sites_dir.glob(SITESPEC_GLOB), key=lambda path: path.name)


def _read_sitespec(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise SiteSpecLoadError(f"cannot read SiteSpec {path.name}: {exc}") from exc
    if not isinstance(doc, dict):
        raise SiteSpecLoadError(f"{path.name}: SiteSpec is not a JSON object")
    return doc


def _validate_identity(path: Path, doc: dict[str, Any]) -> str:
    """Minimal identity validation; full schema meaning lives in #1225-A.

    Only the fields the resolver relies on are checked here so the resolver
    does not re-hard-code the complete SiteSpec schema. Same-SiteSpec legacy
    alias duplicates are rejected here too — the resolver boundary is
    independently fail-closed and does not depend on schema ``uniqueItems``.
    """
    site_id = doc.get("site_id")
    if not isinstance(site_id, str) or not ID_PATTERN.match(site_id):
        raise SiteSpecLoadError(f"{path.name}: invalid site_id {site_id!r}")
    legacy_ids = doc.get("legacy_ids")
    if not isinstance(legacy_ids, list):
        raise SiteSpecLoadError(f"{path.name}: legacy_ids must be an array")
    seen_legacy: set[str] = set()
    for lid in legacy_ids:
        if not isinstance(lid, str) or not ID_PATTERN.match(lid):
            raise SiteSpecLoadError(f"{path.name}: invalid legacy id {lid!r}")
        if lid in seen_legacy:
            raise SiteSpecLoadError(
                f"{path.name}: duplicate legacy id {lid!r} within one SiteSpec"
            )
        seen_legacy.add(lid)
    if site_id in legacy_ids:
        raise SiteSpecLoadError(
            f"{path.name}: canonical site_id {site_id!r} must not appear in legacy_ids"
        )
    return site_id


class SiteSpecResolver:
    """Resolve canonical and legacy site IDs to canonical SiteSpecs.

    Parameters
    ----------
    sites_dir:
        Directory containing ``*.sitespec.json`` files. Defaults to the
        repository ``configs/sites`` directory.
    """

    def __init__(self, sites_dir: Path | str | None = None) -> None:
        self.sites_dir = Path(sites_dir) if sites_dir is not None else CONFIGS_SITES_DIR
        self._by_canonical: dict[str, dict[str, Any]] = {}
        self._by_legacy: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        """(Re)load all canonical SiteSpecs, fail-closed on collisions."""
        paths = iter_sitespec_paths(self.sites_dir)
        if not paths:
            raise SiteSpecLoadError(
                f"no canonical SiteSpec files found in {self.sites_dir}"
            )
        by_canonical: dict[str, dict[str, Any]] = {}
        by_legacy: dict[str, str] = {}
        for path in paths:
            doc = _read_sitespec(path)
            site_id = _validate_identity(path, doc)
            if site_id in by_canonical:
                raise SiteSpecLoadError(f"duplicate canonical site_id {site_id!r}")
            if site_id in by_legacy:
                raise SiteSpecLoadError(
                    f"canonical site_id {site_id!r} collides with another SiteSpec's legacy alias"
                )
            for lid in doc["legacy_ids"]:
                if lid in by_legacy:
                    raise SiteSpecLoadError(
                        f"legacy alias {lid!r} claimed by multiple SiteSpecs"
                    )
                if lid in by_canonical:
                    raise SiteSpecLoadError(
                        f"legacy alias {lid!r} collides with a canonical site_id"
                    )
            by_canonical[site_id] = doc
            for lid in doc["legacy_ids"]:
                by_legacy[lid] = site_id
        self._by_canonical = by_canonical
        self._by_legacy = by_legacy

    @property
    def specs(self) -> Mapping[str, dict[str, Any]]:
        """Canonical site_id → SiteSpec snapshot (deep-copied).

        The returned mapping is a defensive copy: mutating it never mutates
        the resolver's internal canonical state.
        """
        return {
            site_id: copy.deepcopy(doc)
            for site_id, doc in self._by_canonical.items()
        }

    @property
    def canonical_ids(self) -> tuple[str, ...]:
        """Sorted canonical site IDs."""
        return tuple(sorted(self._by_canonical))

    def _resolve_identity(self, identifier: str) -> tuple[str, str, str]:
        """Resolve to ``(requested_id, canonical_site_id, resolution_kind)``.

        Shared by :meth:`resolve` and :meth:`resolve_with_metadata` so the
        canonical/legacy discrimination logic cannot drift between the two
        entry points. ``requested_id`` is the normalized identifier actually
        used for lookup (``.strip()`` applied, matching :meth:`resolve`).
        Fail-closed: empty, malformed, and unknown identifiers raise
        :class:`SiteSpecNotFoundError`; display labels and jurisdiction
        historical aliases never resolve here.
        """
        if not isinstance(identifier, str) or not identifier.strip():
            raise SiteSpecNotFoundError(f"empty site identifier {identifier!r}")
        identifier = identifier.strip()
        if not ID_PATTERN.match(identifier):
            raise SiteSpecNotFoundError(f"invalid site identifier {identifier!r}")
        if identifier in self._by_canonical:
            return identifier, identifier, "canonical"
        canonical_id = self._by_legacy.get(identifier)
        if canonical_id is None:
            raise SiteSpecNotFoundError(f"unknown site identifier {identifier!r}")
        return identifier, canonical_id, "legacy_alias"

    def resolve(self, identifier: str) -> dict[str, Any]:
        """Resolve a canonical or legacy site ID to its canonical SiteSpec.

        Raises
        ------
        SiteSpecNotFoundError
            Empty, malformed, or unknown identifiers. Never falls back.
        """
        _, canonical_id, _ = self._resolve_identity(identifier)
        # Defensive boundary: callers may mutate the returned SiteSpec
        # without corrupting the resolver's internal canonical state.
        return copy.deepcopy(self._by_canonical[canonical_id])

    def resolve_with_metadata(self, identifier: str) -> dict[str, Any]:
        """Resolve like :meth:`resolve` but return alias-resolution metadata.

        Additive observability API (#1225-B.1): the caller learns whether the
        request used the canonical ID or a legacy alias, without any change to
        the plain :meth:`resolve` contract. No telemetry persistence/logging
        is performed here.

        Returns
        -------
        dict
            ``requested_id`` — normalized identifier used for lookup
            ``canonical_site_id`` — canonical SiteSpec ``site_id``
            ``resolution_kind`` — ``"canonical"`` | ``"legacy_alias"``
            ``spec`` — defensive deep copy of the canonical SiteSpec

        Raises
        ------
        SiteSpecNotFoundError
            Same fail-closed behavior as :meth:`resolve`.
        """
        requested_id, canonical_id, resolution_kind = self._resolve_identity(
            identifier
        )
        return {
            "requested_id": requested_id,
            "canonical_site_id": canonical_id,
            "resolution_kind": resolution_kind,
            "spec": copy.deepcopy(self._by_canonical[canonical_id]),
        }


def load_sitespecs(sites_dir: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """Return all canonical SiteSpecs keyed by canonical ``site_id``.

    Collisions (duplicate canonical IDs, cross-SiteSpec legacy alias
    conflicts, canonical-vs-legacy conflicts) raise
    :class:`SiteSpecLoadError` instead of resolving first-match-wins.
    """
    resolver = SiteSpecResolver(sites_dir)
    return dict(resolver.specs)


def resolve_site_id(
    identifier: str,
    sites_dir: Path | str | None = None,
    *,
    resolver: SiteSpecResolver | None = None,
) -> dict[str, Any]:
    """One-shot dual-read resolution of ``identifier`` to a canonical SiteSpec.

    Equivalent to ``SiteSpecResolver(sites_dir).resolve(identifier)`` but
    reuses ``resolver`` when provided.
    """
    if resolver is not None:
        return resolver.resolve(identifier)
    return SiteSpecResolver(sites_dir).resolve(identifier)


def resolve_site_id_with_metadata(
    identifier: str,
    sites_dir: Path | str | None = None,
    *,
    resolver: SiteSpecResolver | None = None,
) -> dict[str, Any]:
    """One-shot alias-resolution metadata variant of :func:`resolve_site_id`.

    Equivalent to ``SiteSpecResolver(sites_dir).resolve_with_metadata(identifier)``
    but reuses ``resolver`` when provided, so a caller with an existing
    resolver never builds a second one.
    """
    if resolver is not None:
        return resolver.resolve_with_metadata(identifier)
    return SiteSpecResolver(sites_dir).resolve_with_metadata(identifier)


# ---------------------------------------------------------------------------
# #1225-E — effective-date jurisdiction resolver
# ---------------------------------------------------------------------------

_JURISDICTION_RESOLUTION_KINDS = frozenset({"canonical", "historical_alias"})


def _parse_jurisdiction_date(value: Any, field: str) -> date:
    """Parse a ``YYYY-MM-DD`` string with stdlib calendar validation.

    Uses :func:`datetime.date.fromisoformat`, so impossible calendar dates
    such as ``2026-02-30`` raise ``ValueError`` and are rejected here as
    fail-closed.
    """
    if not isinstance(value, str):
        raise JurisdictionResolutionError(
            f"{field} must be a string, got {type(value).__name__}"
        )
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise JurisdictionResolutionError(
            f"{field} is not a valid ISO calendar date: {value!r}"
        )


def resolve_jurisdiction_at(spec: dict[str, Any], as_of: str) -> dict[str, Any]:
    """Resolve the jurisdiction name of *spec* that was effective at *as_of*.

    Pure, date-aware helper built on the canonical ``jurisdiction`` block of a
    canonical SiteSpec (see ``configs/sitespec.schema.json``). This is **not**
    a site-ID resolver — historical jurisdiction aliases are legal identity
    snapshots, not runtime site identifiers.

    Parameters
    ----------
    spec:
        A canonical SiteSpec dict (as produced by :func:`resolve_site_id` or
        :attr:`SiteSpecResolver.resolve`). The input object is never mutated.
    as_of:
        Explicit ``YYYY-MM-DD`` date string. **Required** — the current system
        clock is never consulted.

    Returns
    -------
    dict
        ``canonical_site_id`` — the SiteSpec ``site_id``
        ``as_of`` — the date string provided
        ``name`` — the effective jurisdiction name (canonical or historical)
        ``resolution_kind`` — ``"canonical"`` | ``"historical_alias"``
        ``effective_from`` — present when ``resolution_kind == "canonical"``
        ``effective_until`` — present when ``resolution_kind == "historical_alias"``

    Raises
    ------
    JurisdictionResolutionError
        Fail-closed for: non-string/absent ``as_of``, malformed or impossible
        calendar dates (e.g. ``2026-02-30``), missing/empty
        ``canonical_name``, malformed canonical ``effective_from``, malformed
        historical alias ``effective_until``, canonical/historical overlap,
        unrepresented historical gap (zero candidates), and ambiguous timeline
        (two or more historical candidates).
    """
    if not isinstance(as_of, str):
        raise JurisdictionResolutionError(
            "as_of must be an explicit YYYY-MM-DD date string; current clock is "
            "never used"
        )
    as_of_date = _parse_jurisdiction_date(as_of, "as_of")

    if not isinstance(spec, dict):
        raise JurisdictionResolutionError("spec must be a SiteSpec dict")
    site_id = spec.get("site_id")
    if not isinstance(site_id, str) or not site_id:
        raise JurisdictionResolutionError("spec.site_id is missing or empty")

    jurisdiction = spec.get("jurisdiction")
    if not isinstance(jurisdiction, dict):
        raise JurisdictionResolutionError(
            "jurisdiction block is missing or not an object"
        )

    canonical_name = jurisdiction.get("canonical_name")
    if not isinstance(canonical_name, str) or not canonical_name:
        raise JurisdictionResolutionError(
            "jurisdiction.canonical_name is missing or empty"
        )

    effective_from_raw = jurisdiction.get("effective_from")
    canonical_from = _parse_jurisdiction_date(
        effective_from_raw, "jurisdiction.effective_from"
    )

    historical_aliases = jurisdiction.get("historical_aliases", [])
    if not isinstance(historical_aliases, list):
        raise JurisdictionResolutionError(
            "jurisdiction.historical_aliases must be an array"
        )

    parsed_aliases: list[dict[str, Any]] = []
    for entry in historical_aliases:
        if not isinstance(entry, dict):
            raise JurisdictionResolutionError(
                "historical alias entry must be an object"
            )
        value = entry.get("value")
        if not isinstance(value, str) or not value:
            raise JurisdictionResolutionError(
                "historical alias .value is missing or empty"
            )
        effective_until_raw = entry.get("effective_until")
        alias_until = _parse_jurisdiction_date(
            effective_until_raw, "historical alias effective_until"
        )
        parsed_aliases.append(
            {"value": value, "effective_until": alias_until}
        )

    # Overlap guard: a historical alias whose effective_until is on or after
    # the canonical effective_from means the canonical/historical timeline is
    # inconsistent. Fail-closed (never guess).
    for alias in parsed_aliases:
        if alias["effective_until"] >= canonical_from:
            raise JurisdictionResolutionError(
                f"historical alias {alias['value']!r} effective_until "
                f"({alias['effective_until'].isoformat()}) >= canonical "
                f"effective_from ({canonical_from.isoformat()}); "
                "canonical/historical overlap"
            )

    # Canonical branch: as_of on or after the canonical effective_from.
    if as_of_date >= canonical_from:
        return {
            "canonical_site_id": site_id,
            "as_of": as_of,
            "name": canonical_name,
            "resolution_kind": "canonical",
            "effective_from": effective_from_raw,
        }

    # Historical branch: as_of before canonical effective_from.
    # Candidate = historical alias whose effective_until >= as_of.
    candidates = [
        alias for alias in parsed_aliases if alias["effective_until"] >= as_of_date
    ]

    # 2+ candidates: ambiguous timeline (no historical effective_from in
    # current schema → cannot disambiguate). first-match-wins prohibited.
    if len(candidates) > 1:
        raise JurisdictionResolutionError(
            f"ambiguous timeline: {len(candidates)} historical aliases match "
            f"as_of={as_of}; first-match-wins and array-order dependence are "
            "prohibited"
        )

    # 0 candidates: unrepresented historical gap.
    if not candidates:
        raise JurisdictionResolutionError(
            f"no historical alias effective at {as_of}; unrepresented "
            "historical gap"
        )

    # Exactly 1 candidate: resolved.
    chosen = candidates[0]
    return {
        "canonical_site_id": site_id,
        "as_of": as_of,
        "name": chosen["value"],
        "resolution_kind": "historical_alias",
        "effective_until": chosen["effective_until"].isoformat(),
    }
