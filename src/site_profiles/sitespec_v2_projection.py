"""Offline Buk-gu v1 SiteSpec -> SiteSpec v2 projection proof (#1287 Slice C).

Pure stdlib only (no new dependency). This is a deterministic, generic-shaped pure
function that projects an existing Buk-gu v1 canonical SiteSpec plus its YAML operational
profile into a generic SiteSpec v2 object. It performs NO resident runtime switch, NO
Cloudflare wiring, NO capability detection, NO live network, and NO Production promotion.

The projection is identity/parity only:

    v1 SiteSpec (canonical identity / legacy aliases / display / public domains / municipality
                jurisdiction / runtime+clone compatibility metadata)
        + YAML SiteProfile (authoritative base_url, allowed_domains)
        -> deterministic offline SiteSpec v2

v1 runtime/clone metadata is deliberately KEPT OUT of the v2 core. It can be extracted
separately via ``extract_v1_compatibility_metadata`` for compatibility assertions, but the
v2 object does not require or invent those fields.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping
from urllib.parse import urlsplit

V2_SCHEMA_VERSION = "2.0.0"

DEFAULT_V1_SOURCE_REF = "configs/sites/bukgu_gwangju.sitespec.json"
DEFAULT_PROFILE_SOURCE_REF = "configs/sites/bukgu_gwangju.yml"

V2_SCHEMA_REF = "configs/platform/site-spec-v2.schema.json"

REQUIRED_JURISDICTION_FIELDS = (
    "canonical_name",
    "short_name",
    "effective_from",
    "historical_aliases",
)


class ProjectionError(Exception):
    """Raised when a v1 -> v2 projection cannot be performed fail-closed."""


def _require(cond, msg):
    if not cond:
        raise ProjectionError(msg)


def project_v1_sitespec_to_v2(
    v1_sitespec: Mapping[str, Any],
    yaml_profile: Mapping[str, Any],
    *,
    v1_source_ref: str,
    profile_source_ref: str,
) -> dict:
    """Project a v1 canonical SiteSpec + YAML profile into a SiteSpec v2 document.

    Fail-closed: any identity/domain/homepage/jurisdiction inconsistency raises
    ``ProjectionError``. Input dicts are never mutated.
    """
    _require(isinstance(v1_sitespec, dict), "v1_sitespec must be a mapping")
    _require(isinstance(yaml_profile, dict), "yaml_profile must be a mapping")

    # ---- identity consistency (v1 vs YAML) ----
    v1_site_id = v1_sitespec.get("site_id")
    yaml_site_id = yaml_profile.get("site_id")
    _require(isinstance(v1_site_id, str) and v1_site_id, "v1 site_id required")
    if yaml_site_id is not None and yaml_site_id != v1_site_id:
        raise ProjectionError(
            f"site_id mismatch: v1={v1_site_id!r} yaml={yaml_site_id!r}"
        )

    # ---- domains: exact parity, no silent expansion ----
    v1_public = v1_sitespec.get("domains", {}).get("public")
    _require(isinstance(v1_public, list) and len(v1_public) >= 1,
             "v1 domains.public must be a non-empty array")
    v1_public = list(v1_public)
    yaml_allowed = yaml_profile.get("allowed_domains")
    _require(isinstance(yaml_allowed, list), "yaml allowed_domains must be an array")
    if set(v1_public) != set(yaml_allowed):
        raise ProjectionError(
            "YAML allowed_domains drift from v1 public domains: "
            f"{set(yaml_allowed)} != {set(v1_public)}"
        )

    # ---- homepage: authoritative YAML base_url, host must be declared ----
    base_url = yaml_profile.get("base_url")
    _require(isinstance(base_url, str) and base_url, "yaml base_url required")
    parsed = urlsplit(base_url)
    _require(parsed.scheme in ("http", "https"),
             f"homepage base_url must be absolute http(s): {base_url!r}")
    _require(bool(parsed.hostname), f"homepage base_url must have a host: {base_url!r}")
    _require(parsed.hostname in v1_public,
             f"homepage host {parsed.hostname!r} not declared in v1 public domains")

    # ---- municipality jurisdiction: lossless parity ----
    jurisdiction = v1_sitespec.get("jurisdiction")
    _require(isinstance(jurisdiction, dict), "v1 jurisdiction required for municipality projection")
    for field in REQUIRED_JURISDICTION_FIELDS:
        _require(field in jurisdiction, f"v1 jurisdiction missing {field}")

    # ---- build v2 (no runtime/clone metadata inside core) ----
    v2 = {
        "$schema": V2_SCHEMA_REF,
        "schema_version": V2_SCHEMA_VERSION,
        "identity": {
            "site_id": v1_site_id,
            "legacy_ids": deepcopy(v1_sitespec.get("legacy_ids", [])),
            "display": deepcopy(v1_sitespec["display"]),
        },
        "domains": {
            "public": deepcopy(v1_public),
        },
        "entry_points": [
            {
                "id": "homepage",
                "kind": "homepage",
                "url": base_url,
            }
        ],
        "archetype": {
            "id": "municipality",
            "state": "configured",
            "confidence": 1.0,
            "evidence_refs": [v1_source_ref],
        },
        "capabilities": [],
        "capture_policy": {
            "acquisition_mode": "offline_fixture",
            "live_network_authorized": False,
        },
        "browser_policy": {
            "surface_mode": "generated_preview",
            "actual_site_control_authorized": False,
        },
        "knowledge_policy": {
            "grounding_required": True,
            "provenance_required": True,
        },
        "action_policy": {
            "external_write_authorized": False,
            "high_risk_actions_authorized": False,
        },
        "provenance": {
            "source_refs": [v1_source_ref, profile_source_ref],
            "review_state": "reviewed",
        },
        "extensions": {
            "municipality": {
                "jurisdiction": deepcopy(jurisdiction),
            }
        },
    }
    return v2


def extract_v1_compatibility_metadata(v1_sitespec: Mapping[str, Any]) -> dict:
    """Extract v1 runtime/clone compatibility metadata OUTSIDE the v2 core.

    This is compatibility evidence only; it is NOT part of a SiteSpec v2 instance and
    the v2 projection validity does not depend on it. Fails closed if the current Buk-gu
    v1 compatibility metadata is missing/malformed.
    """
    _require(isinstance(v1_sitespec, dict), "v1_sitespec must be a mapping")
    runtime = v1_sitespec.get("runtime")
    _require(
        isinstance(runtime, dict)
        and "python_profile" in runtime
        and "cloudflare_adapter" in runtime,
        "v1 runtime compatibility metadata missing/malformed",
    )
    clone = v1_sitespec.get("clone")
    _require(
        isinstance(clone, dict)
        and "golden_commit" in clone
        and "golden_commit_subject" in clone,
        "v1 clone compatibility metadata missing/malformed",
    )
    return {
        "runtime": deepcopy(runtime),
        "clone": deepcopy(clone),
    }
