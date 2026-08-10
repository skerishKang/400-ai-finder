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
from pathlib import Path
from typing import Any, Mapping

CONFIGS_SITES_DIR = Path(__file__).resolve().parent.parent.parent / "configs" / "sites"

SITESPEC_GLOB = "*.sitespec.json"

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class SiteSpecError(Exception):
    """Base error for canonical SiteSpec loading and resolution."""


class SiteSpecLoadError(SiteSpecError):
    """The canonical SiteSpec set is malformed or self-inconsistent."""


class SiteSpecNotFoundError(SiteSpecError, KeyError):
    """An identifier does not resolve to any canonical SiteSpec."""


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

    def resolve(self, identifier: str) -> dict[str, Any]:
        """Resolve a canonical or legacy site ID to its canonical SiteSpec.

        Raises
        ------
        SiteSpecNotFoundError
            Empty, malformed, or unknown identifiers. Never falls back.
        """
        if not isinstance(identifier, str) or not identifier.strip():
            raise SiteSpecNotFoundError(f"empty site identifier {identifier!r}")
        identifier = identifier.strip()
        if not ID_PATTERN.match(identifier):
            raise SiteSpecNotFoundError(f"invalid site identifier {identifier!r}")
        doc = self._by_canonical.get(identifier)
        if doc is not None:
            # Defensive boundary: callers may mutate the returned SiteSpec
            # without corrupting the resolver's internal canonical state.
            return copy.deepcopy(doc)
        canonical_id = self._by_legacy.get(identifier)
        if canonical_id is None:
            raise SiteSpecNotFoundError(f"unknown site identifier {identifier!r}")
        return copy.deepcopy(self._by_canonical[canonical_id])


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
