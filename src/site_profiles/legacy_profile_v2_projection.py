"""Offline legacy YAML profile -> SiteSpec v2 candidate + onboarding report (#1232).

Pure stdlib only (no new dependency). This is a GENERIC, site-id-agnostic pure function
that projects an existing legacy YAML SiteProfile (e.g. seogu_gwangju) into a generic
SiteSpec v2 *candidate* plus an offline onboarding report, using only checked-in static
evidence (board_patterns, document_extensions, important_keywords, base_url,
allowed_domains).

It deliberately does NOT:
- perform any live network / crawl / Firecrawl / API call;
- branch on a specific site_id (e.g. ``if site_id == "seogu"``);
- reuse or extend the Buk-gu ``project_v1_sitespec_to_v2`` projector (that needs a v1
  canonical SiteSpec + municipality jurisdiction);
- fabricate a municipality jurisdiction / effective-date (when the canonical jurisdiction
  is missing, it is reported as a ``source_or_provenance_gap`` exception instead).

The result is a candidate, not a finalized v2 SiteSpec: a real municipality that has no
checked-in canonical jurisdiction keeps ``archetype.id = municipality`` (correct
classification prior) with ``state = review_required`` and an explicit exception, and its
v2 core does NOT carry a fabricated ``extensions.municipality.jurisdiction``.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping
from urllib.parse import urlsplit

V2_SCHEMA_VERSION = "2.0.0"
V2_SCHEMA_REF = "configs/platform/site-spec-v2.schema.json"

MUNICIPAL_NAME_SUFFIX = re.compile(r"(시청|군청|구청|도청|광역시|특별시)$")
UNIVERSITY_NAME_SUFFIX = re.compile(r"(대학교|대학)$")
BANK_NAME_SUFFIX = re.compile(r"(은행|뱅크)$")

NOTICE_KEYWORDS = ("공지사항", "고시공고", "새소식", "공고")


class LegacyProfileProjectionError(Exception):
    """Raised when a legacy-profile -> v2 projection cannot be performed fail-closed."""


def _require(cond, msg):
    if not cond:
        raise LegacyProfileProjectionError(msg)


def _infer_archetype(name: str | None, classification: str | None) -> str:
    """Generic archetype prior from municipal/university/bank name signals.

    This is a classification prior, NOT a fabricated jurisdiction. Sites with no
    recognizable signal fall back to ``unknown`` rather than being coerced.
    """
    n = (name or "").strip()
    if MUNICIPAL_NAME_SUFFIX.search(n):
        return "municipality"
    if classification and "MUNICIPAL" in str(classification).upper():
        return "municipality"
    if UNIVERSITY_NAME_SUFFIX.search(n):
        return "university"
    if BANK_NAME_SUFFIX.search(n):
        return "bank"
    return "unknown"


def _derive_capabilities(
    profile: Mapping[str, Any],
    homepage_id: str,
    source_ref: str,
) -> list[dict]:
    """Evidence-backed capability candidates from offline YAML profile fields.

    Keyword-only evidence (e.g. 조직도) yields ``review_required`` rather than a
    confident claim. No URLs are fabricated; every capability references the homepage.
    """
    caps: list[dict] = []
    board_patterns = profile.get("board_patterns") or []
    keywords = profile.get("important_keywords") or []
    doc_ext = profile.get("document_extensions") or []
    bp_text = " ".join(board_patterns)
    kw_text = " ".join(keywords)

    has_notice_signal = any(k in kw_text for k in NOTICE_KEYWORDS) or (
        "list.do" in bp_text or "notice" in bp_text or "board" in bp_text
    )
    if has_notice_signal:
        caps.append(
            {
                "id": "notice_board",
                "state": "detected",
                "confidence": 0.85,
                "safety_level": "navigate",
                "entry_points": [homepage_id],
                "evidence_refs": [source_ref],
            }
        )

    has_doc_signal = bool(doc_ext) or "boardDownload.es" in bp_text or "document" in bp_text
    if has_doc_signal:
        caps.append(
            {
                "id": "document_library",
                "state": "detected",
                "confidence": 0.8,
                "safety_level": "navigate",
                "entry_points": [homepage_id],
                "evidence_refs": [source_ref],
            }
        )

    # 조직도 (org chart) keyword-only evidence -> review_required, low confidence.
    if "조직도" in kw_text:
        caps.append(
            {
                "id": "directory",
                "state": "review_required",
                "confidence": 0.3,
                "safety_level": "read_only",
                "entry_points": [homepage_id],
                "evidence_refs": [source_ref],
            }
        )

    return caps


def legacy_profile_to_v2_candidate(
    yaml_profile: Mapping[str, Any],
    *,
    source_ref: str,
) -> dict:
    """Project a legacy YAML SiteProfile into a generic SiteSpec v2 candidate.

    Fail-closed: any identity/homepage inconsistency raises
    ``LegacyProfileProjectionError``. Input dict is never mutated.
    """
    _require(isinstance(yaml_profile, dict), "yaml_profile must be a mapping")

    site_id = yaml_profile.get("site_id")
    _require(isinstance(site_id, str) and site_id, "profile site_id required")
    display_label = yaml_profile.get("name") or site_id

    public = yaml_profile.get("allowed_domains")
    _require(isinstance(public, list) and len(public) >= 1,
             "profile allowed_domains must be a non-empty array")

    base_url = yaml_profile.get("base_url")
    _require(isinstance(base_url, str) and base_url, "profile base_url required")
    parsed = urlsplit(base_url)
    _require(parsed.scheme in ("http", "https"),
             f"base_url must be absolute http(s): {base_url!r}")
    _require(bool(parsed.hostname), f"base_url must have a host: {base_url!r}")
    _require(parsed.hostname in set(public),
             f"homepage host {parsed.hostname!r} not declared in allowed_domains")

    archetype_id = _infer_archetype(display_label, yaml_profile.get("classification"))

    candidate = {
        "$schema": V2_SCHEMA_REF,
        "schema_version": V2_SCHEMA_VERSION,
        "identity": {
            "site_id": site_id,
            "legacy_ids": deepcopy(yaml_profile.get("legacy_ids", []) or []),
            "display": {
                "default_label": display_label,
                "locale_labels": {"ko": display_label},
            },
        },
        "domains": {
            "public": deepcopy(public),
        },
        "entry_points": [
            {
                "id": "homepage",
                "kind": "homepage",
                "url": base_url,
            }
        ],
        "archetype": {
            # A real municipality with no checked-in canonical jurisdiction is a
            # prior, not a configured fact -> review_required, not fabricated.
            "id": archetype_id,
            "state": "review_required" if archetype_id == "municipality" else "detected",
            "confidence": 0.6 if archetype_id == "municipality" else 0.7,
            "evidence_refs": [source_ref],
        },
        "capabilities": _derive_capabilities(yaml_profile, "homepage", source_ref),
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
            "source_refs": [source_ref],
            # Static offline evidence, not a reviewed v1->v2 projection.
            "review_state": "synthetic",
        },
        # No municipality jurisdiction is fabricated when none is checked in.
        "extensions": {},
    }
    return candidate


def legacy_profile_to_onboarding_report(
    candidate: Mapping[str, Any],
    yaml_profile: Mapping[str, Any],
    *,
    source_ref: str,
    run_id: str,
) -> dict:
    """Build a deterministic offline onboarding report for a v2 candidate.

    Ratios are computed deterministically from capability states plus the jurisdiction
    gap item, and always sum to 1.0 within tolerance.
    """
    _require(isinstance(candidate, dict), "candidate must be a mapping")
    site_id = candidate["identity"]["site_id"]
    display_label = candidate["identity"]["display"]["default_label"]
    archetype = candidate["archetype"]
    capabilities = candidate["capabilities"]

    exceptions: list[dict] = []

    # Requirement: missing canonical municipality jurisdiction -> source_or_provenance_gap.
    if archetype["id"] == "municipality" and "municipality" not in candidate.get("extensions", {}):
        exceptions.append(
            {
                "id": "exc_missing_canonical_jurisdiction",
                "category": "source_or_provenance_gap",
                "severity": "warning",
                "review_state": "review_required",
                "summary": (
                    "Canonical municipality jurisdiction (effective-date) is not present in "
                    "any checked-in v1 SiteSpec; extensions.municipality.jurisdiction omitted "
                    "(no fabrication)."
                ),
                "affected_refs": [site_id],
            }
        )

    # Requirement: org-chart / keyword-only evidence -> explicit exception.
    for cap in capabilities:
        if cap.get("state") == "review_required":
            exceptions.append(
                {
                    "id": f"exc_review_{cap['id']}",
                    "category": "low_confidence_classification",
                    "severity": "warning",
                    "review_state": "review_required",
                    "summary": (
                        f"Capability {cap['id']} derived from keyword-only evidence "
                        f"(조직도); explicit human review required."
                    ),
                    "affected_refs": [cap["id"]],
                }
            )

    # Deterministic ratio accounting: capabilities + 1 jurisdiction-gap item.
    n_items = len(capabilities) + 1
    auto = sum(
        1 for c in capabilities if c.get("state") in ("configured", "detected")
    ) / n_items
    review = (
        sum(1 for c in capabilities if c.get("state") == "review_required") / n_items
    )
    # The +1 jurisdiction-gap item accounts for the unsupported/unsourceable slice.
    unsupported = (1 / n_items) if exceptions else 0.0
    # Renormalize so the three always sum to exactly 1.0.
    total = auto + review + unsupported
    auto = auto / total
    review = review / total
    unsupported = unsupported / total

    return {
        "schema_version": V2_SCHEMA_VERSION,
        "run_id": run_id,
        "input": {
            "source_kind": "offline_fixture",
            "source_refs": [source_ref],
        },
        "acquisition": {
            "acquisition_mode": "offline_fixture",
            "live_network_authorized": False,
        },
        "site_identity": {
            "site_id": site_id,
            "display_label": display_label,
        },
        "archetype": deepcopy(archetype),
        "capabilities": deepcopy(capabilities),
        "artifacts": [],
        "metrics": {
            "automation_ratio": auto,
            "human_review_ratio": review,
            "unsupported_ratio": unsupported,
        },
        "exceptions": exceptions,
        "provenance": {
            "source_refs": [source_ref],
            "review_state": "synthetic",
        },
        "change_scope": {
            "shared_core_changed": False,
        },
        "promotion": {
            "production_promotion_requested": False,
        },
    }
