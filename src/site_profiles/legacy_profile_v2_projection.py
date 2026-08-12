"""Offline legacy YAML profile -> pre-SiteSpec v2 candidate + onboarding report (#1232).

Pure stdlib only (no new dependency). This is a GENERIC, site-id-agnostic pure function
that projects an existing legacy YAML SiteProfile (e.g. seogu_gwangju) into a generic
SiteSpec v2 *candidate* plus an offline onboarding report, using only checked-in static
evidence.

IMPORTANT CONTRACT BOUNDARY: the output is a PRE-SITESPEC ONBOARDING CANDIDATE, not a
final valid SiteSpec v2. A real municipality that has no checked-in canonical jurisdiction
keeps ``archetype.id = municipality`` (correct classification prior) with
``state = review_required`` and an explicit ``source_or_provenance_gap`` exception, and its
v2 core does NOT carry a fabricated ``extensions.municipality.jurisdiction``. It must not be
passed through the authoritative Slice-B ``validate_site_spec_v2`` as if final, and it is not
promoted until the required canonical typed extension is acquired.

This module deliberately does NOT:
- perform any live network / crawl / Firecrawl / API call;
- branch on a specific site_id (e.g. ``if site_id == "seogu"``);
- reuse or extend the Buk-gu ``project_v1_sitespec_to_v2`` projector;
- claim/detect a capability from keyword-only or extension-list-only signals.

Capability evidence rule (offline, observed-only):
- ``notice_board`` is ``detected`` ONLY when explicit observed board/list URLs are supplied
  (e.g. ``bbs/BBSMSTR.../list.do``); a ``공지사항``/``고시공고`` keyword alone is NOT sufficient.
- ``document_library`` is ``detected`` ONLY when explicit observed download/document URLs are
  supplied (e.g. ``boardDownload.es``); ``document_extensions`` alone is NOT sufficient.
- ``조직도`` (org-chart) keyword-only evidence yields ``directory`` with ``state=review_required``.
Observed evidence is supplied via the site-id-agnostic ``observed_evidence`` argument (a list
of URL/evidence strings). No network call is ever made to obtain it.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

V2_SCHEMA_VERSION = "2.0.0"
V2_SCHEMA_REF = "configs/platform/site-spec-v2.schema.json"

MUNICIPAL_NAME_SUFFIX = re.compile(r"(시청|군청|구청|도청|광역시|특별시)$")
UNIVERSITY_NAME_SUFFIX = re.compile(r"(대학교|대학)$")
BANK_NAME_SUFFIX = re.compile(r"(은행|뱅크)$")

NOTICE_KEYWORDS = ("공지사항", "고시공고", "새소식", "공고")

# Observed-URL patterns that justify a detected capability (NOT keyword-only).
NOTICE_OBSERVED_PATTERNS = ("bbs/BBSMSTR", "list.do", "boardList.do", "boardView.do")
DOC_OBSERVED_PATTERNS = ("boardDownload.es", "download")


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


def _observed_urls_match(observed: Sequence[str], patterns: Sequence[str]) -> list[str]:
    """Return observed evidence URLs (site-id-agnostic) matching any of ``patterns``.

    Both the URL and the patterns are case-normalized before comparison so that a
    mixed-case observed URL (e.g. ``/bbs/BBSMSTR_...``) or pattern (e.g. ``boardDownload.es``)
    is never missed by case-sensitive substring matching. Matched URLs are returned in
    their original (declared) case for provenance/evidence fidelity.
    """
    if not observed:
        return []
    norm_patterns = [p.lower() for p in patterns]
    matched = []
    for url in observed:
        u = (url or "").lower()
        if any(pat in u for pat in norm_patterns):
            matched.append(url)
    return matched


def _validate_observed_evidence(
    observed: Sequence[str], allowed_domains: Sequence[str]
) -> None:
    """Fail-closed validation of every observed-evidence URL BEFORE capability detection.

    Each item must:
    - be a non-empty string;
    - parse via ``urlsplit``;
    - use an ``http``/``https`` scheme;
    - carry a hostname;
    - have that hostname exactly declared in ``allowed_domains``.

    External-domain / non-http / relative / malformed evidence raises
    ``LegacyProfileProjectionError`` instead of being silently ignored: observed evidence
    outside the declared scope must never leak into a capability claim.
    """
    declared = set(allowed_domains)
    for item in observed:
        if not isinstance(item, str) or not item.strip():
            raise LegacyProfileProjectionError(
                f"observed_evidence item must be a non-empty string: {item!r}"
            )
        parts = urlsplit(item)
        if parts.scheme not in ("http", "https"):
            raise LegacyProfileProjectionError(
                f"observed_evidence must use an http(s) scheme, got {item!r}"
            )
        if not parts.hostname:
            raise LegacyProfileProjectionError(
                f"observed_evidence must declare a hostname, got {item!r}"
            )
        if parts.hostname not in declared:
            raise LegacyProfileProjectionError(
                f"observed_evidence host {parts.hostname!r} is not declared in "
                f"allowed_domains {sorted(declared)!r}: {item!r}"
            )


def _derive_capabilities(
    profile: Mapping[str, Any],
    homepage_id: str,
    source_ref: str,
    observed_evidence: Sequence[str],
    observed_source_refs: Sequence[str] | None = None,
) -> list[dict]:
    """Evidence-backed capability candidates from OFFLINE OBSERVED evidence only.

    Keyword-only signals (e.g. 조직도) yield ``review_required`` rather than a confident
    claim. No URLs are fabricated; every capability references the homepage.

    ``observed_source_refs`` are static/checked-in provenance pointers for the observed
    evidence (e.g. the test that records the observed URLs). They are attached to each
    observed-backed capability's ``evidence_refs`` and to the candidate ``provenance``.
    Keyword-only (directory) capability evidence stays YAML-only.
    """
    caps: list[dict] = []
    obs_refs = list(observed_source_refs or [])

    notice_matches = _observed_urls_match(observed_evidence, NOTICE_OBSERVED_PATTERNS)
    if notice_matches:
        caps.append(
            {
                "id": "notice_board",
                "state": "detected",
                "confidence": 0.85,
                "safety_level": "navigate",
                "entry_points": [homepage_id],
                # Real checked-in observed evidence URL(s) identify the source.
                "evidence_refs": [source_ref, *obs_refs, *notice_matches],
            }
        )

    doc_matches = _observed_urls_match(observed_evidence, DOC_OBSERVED_PATTERNS)
    if doc_matches:
        caps.append(
            {
                "id": "document_library",
                "state": "detected",
                "confidence": 0.8,
                "safety_level": "navigate",
                "entry_points": [homepage_id],
                "evidence_refs": [source_ref, *obs_refs, *doc_matches],
            }
        )

    # 조직도 (org chart) keyword-only evidence -> review_required, low confidence.
    # (deliberately NOT promoted to detected; no observed org-chart URL required)
    keywords = profile.get("important_keywords") or []
    kw_text = " ".join(keywords)
    if "조직도" in kw_text:
        caps.append(
            {
                "id": "directory",
                "state": "review_required",
                "confidence": 0.3,
                "safety_level": "read_only",
                "entry_points": [homepage_id],
                # Keyword-only evidence -> YAML source ref only.
                "evidence_refs": [source_ref],
            }
        )

    return caps


def legacy_profile_to_v2_candidate(
    yaml_profile: Mapping[str, Any],
    *,
    source_ref: str,
    observed_evidence: Sequence[str] | None = None,
    observed_source_refs: Sequence[str] | None = None,
) -> dict:
    """Project a legacy YAML SiteProfile into a generic pre-SiteSpec v2 candidate.

    ``observed_evidence`` is a site-id-agnostic list of checked-in offline observed URLs
    (e.g. board/list/download patterns). Capability detection requires it; passing ``None``
    yields no observed-backed capabilities. ``observed_source_refs`` are static/checked-in
    provenance pointers (e.g. the test that records the observed URLs) attached to the
    observed-backed capabilities and to the candidate ``provenance``.

    Fail-closed: any identity/homepage inconsistency OR any out-of-scope observed-evidence
    URL (non-http scheme, no host, or host not in ``allowed_domains``) raises
    ``LegacyProfileProjectionError``. Input dict is never mutated.
    """
    _require(isinstance(yaml_profile, dict), "yaml_profile must be a mapping")

    site_id = yaml_profile.get("site_id")
    _require(isinstance(site_id, str) and site_id, "profile site_id required")
    display_label = yaml_profile.get("name") or site_id

    public = yaml_profile.get("allowed_domains")
    _require(isinstance(public, list) and len(public) >= 1,
             "profile allowed_domains must be a non-empty array")

    # Fail-closed: validate observed evidence scope BEFORE capability detection.
    if observed_evidence is not None:
        _validate_observed_evidence(list(observed_evidence), public)

    base_url = yaml_profile.get("base_url")
    _require(isinstance(base_url, str) and base_url, "profile base_url required")
    parsed = urlsplit(base_url)
    _require(parsed.scheme in ("http", "https"),
              f"base_url must be absolute http(s): {base_url!r}")
    _require(bool(parsed.hostname), f"base_url must have a host: {base_url!r}")
    _require(parsed.hostname in set(public),
              f"homepage host {parsed.hostname!r} not declared in allowed_domains")

    archetype_id = _infer_archetype(display_label, yaml_profile.get("classification"))

    # Archetype state: unknown stays unknown; a prior without a checked-in canonical
    # jurisdiction is review_required; other recognized priors are detected.
    if archetype_id == "unknown":
        arch_state = "unknown"
        arch_conf = 0.2
    elif archetype_id == "municipality":
        arch_state = "review_required"
        arch_conf = 0.6
    else:
        arch_state = "detected"
        arch_conf = 0.7

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
            "id": archetype_id,
            "state": arch_state,
            "confidence": arch_conf,
            "evidence_refs": [source_ref],
        },
        "capabilities": _derive_capabilities(
            yaml_profile, "homepage", source_ref, observed_evidence or [],
            observed_source_refs,
        ),
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
            "source_refs": [source_ref, *(observed_source_refs or [])],
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
    observed_source_refs: Sequence[str] | None = None,
) -> dict:
    """Build a deterministic offline onboarding report for a pre-SiteSpec v2 candidate.

    Ratio accounting counts only real accounting items:
    - configured/detected capability -> automation
    - review_required capability -> human_review
    - unsupported/not_detected capability -> unsupported
    - municipality + missing canonical jurisdiction -> one extra unsupported (jurisdiction gap)
    Non-municipality sites never get a fabricated jurisdiction slot. A zero-denominator case
    (unknown site, no capabilities) is handled explicitly (unsupported_ratio = 1.0).
    Ratios always sum to 1.0 within tolerance.
    """
    _require(isinstance(candidate, dict), "candidate must be a mapping")
    site_id = candidate["identity"]["site_id"]
    display_label = candidate["identity"]["display"]["default_label"]
    archetype = candidate["archetype"]
    capabilities = candidate["capabilities"]

    # Combined YAML + checked-in static observed-evidence source refs.
    source_refs = [source_ref, *(observed_source_refs or [])]

    exceptions: list[dict] = []

    # Missing canonical municipality jurisdiction -> source_or_provenance_gap.
    if archetype["id"] == "municipality" and "municipality" not in candidate.get("extensions", {}):
        exceptions.append(
            {
                "id": "exc_missing_canonical_jurisdiction",
                "category": "source_or_provenance_gap",
                "severity": "warning",
                "review_state": "review_required",
                "summary": (
                    "Pre-SiteSpec candidate: canonical municipality jurisdiction "
                    "(effective-date) is not present in any checked-in v1 SiteSpec; "
                    "extensions.municipality.jurisdiction omitted (no fabrication)."
                ),
                "affected_refs": [site_id],
            }
        )

    # Org-chart / keyword-only evidence -> explicit exception.
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

    # Deterministic ratio accounting over real items only.
    auto = sum(1 for c in capabilities if c.get("state") in ("configured", "detected"))
    review = sum(1 for c in capabilities if c.get("state") == "review_required")
    unsupported = sum(
        1 for c in capabilities if c.get("state") in ("unsupported", "not_detected")
    )
    # Jurisdiction gap only for a municipality missing its canonical jurisdiction.
    if archetype["id"] == "municipality" and "municipality" not in candidate.get("extensions", {}):
        unsupported += 1

    total = auto + review + unsupported
    if total == 0:
        # Explicit zero-denominator handling: nothing can be onboarded -> unsupported.
        auto_r = 0.0
        review_r = 0.0
        unsupported_r = 1.0
    else:
        auto_r = auto / total
        review_r = review / total
        unsupported_r = unsupported / total

    return {
        "schema_version": V2_SCHEMA_VERSION,
        "run_id": run_id,
        "input": {
            "source_kind": "offline_fixture",
            "source_refs": source_refs,
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
            "automation_ratio": auto_r,
            "human_review_ratio": review_r,
            "unsupported_ratio": unsupported_r,
        },
        "exceptions": exceptions,
        "provenance": {
            "source_refs": source_refs,
            "review_state": "synthetic",
        },
        "change_scope": {
            "shared_core_changed": False,
        },
        "promotion": {
            "production_promotion_requested": False,
        },
    }
