"""Offline generic Site Model bundle builder (#1232).

Pure deterministic function. No network, no provider, no filesystem reads in
production code, no time/random. Reuses:

- ``src.indexer.document_indexer.DocumentIndexer.build_index`` as the authoritative
  document-inventory primitive;
- a candidate produced by ``src.site_profiles.legacy_profile_v2_projection`` (read-only).

The test layer (NOT production code) is responsible for constructing the in-memory
``homepage_map`` from ``HomepageMapper.extract_menu_links``. This module never invokes
any crawler, fetch provider, or URL classifier of its own.

This slice models bounded routes + documents + read/navigation-only action graph and
produces a QA-ready manifest. It does NOT render a preview, fabricate content, or
execute any action.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from src.indexer.document_indexer import DocumentIndexer, make_canonical_url

BUNDLE_VERSION = "1.0.0"
ROOT_ROUTE_ID = "route-homepage"

# Navigation-only action types allowed in this offline slice.
OFFLINE_ALLOWED_ACTION_TYPES = {"navigate"}

# Forbidden anywhere in the offline action graph.
FORBIDDEN_ACTION_TYPES = {
    "click",
    "input",
    "type",
    "select",
    "prefill",
    "submit",
    "login",
    "payment",
    "pay",
    "upload",
    "enter_identity",
    "external_write",
}


class OfflineSiteModelError(Exception):
    """Raised when an offline site-model bundle cannot be built fail-closed."""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise OfflineSiteModelError(msg)


# --------------------------------------------------------------------------- #
# Candidate safety validation
# --------------------------------------------------------------------------- #


def _validate_candidate(
    candidate: Mapping[str, Any], homepage_map_source_ref: str
) -> tuple[str, list[str], list[str], str]:
    """Fail-closed validation of the pre-SiteSpec v2 candidate.

    Returns (site_id, allowed_domains, provenance_source_refs, homepage_url).
    """
    _require(isinstance(candidate, dict), "candidate must be a mapping")

    identity = candidate.get("identity") or {}
    site_id = identity.get("site_id")
    _require(isinstance(site_id, str) and site_id, "identity.site_id required")

    domains = candidate.get("domains") or {}
    public = domains.get("public")
    _require(
        isinstance(public, list) and len(public) >= 1,
        "domains.public must be a non-empty list",
    )

    prov = candidate.get("provenance")
    _require(isinstance(prov, dict), "candidate provenance object required")
    refs = prov.get("source_refs")
    _require(
        isinstance(refs, list) and len(refs) >= 1,
        "provenance.source_refs must be a non-empty list",
    )
    for r in refs:
        _require(
            isinstance(r, str) and r.strip(),
            f"provenance source_ref must be a non-empty string, got {r!r}",
        )

    # Homepage entry point must exist and its host declared in domains.public.
    eps = candidate.get("entry_points") or []
    homepage = next((e for e in eps if e.get("id") == "homepage"), None)
    _require(homepage is not None, "candidate homepage entry point required")
    hp_url = homepage.get("url")
    _require(
        isinstance(hp_url, str) and hp_url, "candidate homepage entry point url required"
    )
    hp_host = urlsplit(hp_url).hostname
    _require(
        hp_host in set(public),
        f"candidate homepage host {hp_host!r} not declared in domains.public",
    )

    cp = candidate.get("capture_policy") or {}
    _require(
        cp.get("acquisition_mode") == "offline_fixture",
        "capture_policy.acquisition_mode must be offline_fixture",
    )
    _require(
        cp.get("live_network_authorized") is False,
        "capture_policy.live_network_authorized must be false",
    )

    bp = candidate.get("browser_policy") or {}
    _require(
        bp.get("actual_site_control_authorized") is False,
        "browser_policy.actual_site_control_authorized must be false",
    )

    ap = candidate.get("action_policy") or {}
    _require(
        ap.get("external_write_authorized") is False,
        "action_policy.external_write_authorized must be false",
    )
    _require(
        ap.get("high_risk_actions_authorized") is False,
        "action_policy.high_risk_actions_authorized must be false",
    )

    # homepage_map_source_ref must be a non-empty string already present in the
    # candidate provenance. This forbids the caller from injecting provenance that
    # drifts from the candidate.
    _require(
        isinstance(homepage_map_source_ref, str) and homepage_map_source_ref.strip(),
        "homepage_map_source_ref must be a non-empty string",
    )
    _require(
        homepage_map_source_ref in refs,
        "homepage_map_source_ref must already exist in candidate.provenance.source_refs",
    )

    return site_id, list(public), list(refs), hp_url


# --------------------------------------------------------------------------- #
# Capture URL allowlist validation
# --------------------------------------------------------------------------- #


def _observed_canon_set(homepage_map: Mapping[str, Any]) -> set[str]:
    obs: set[str] = set()
    hp = homepage_map.get("homepage") or {}
    for item in (hp.get("navigation_links") or []) + (hp.get("attachment_links") or []):
        u = item.get("url") if isinstance(item, dict) else ""
        if u:
            obs.add(make_canonical_url(u))
    for item in (homepage_map.get("sitemap") or {}).get("urls", []):
        u = item.get("url") if isinstance(item, dict) else ""
        if u:
            obs.add(make_canonical_url(u))
    return obs


def _validate_capture_urls(
    capture_urls: Sequence[str],
    public: Sequence[str],
    observed: set[str],
) -> list[str]:
    """Validate + deterministically deduplicate the explicit capture allowlist.

    Each capture URL must be absolute http(s), its host must be declared in
    ``domains.public``, and it must actually be observed in the supplied
    ``homepage_map``. Missing/relative/malformed/cross-domain/unobserved URLs fail
    closed. Duplicate canonical URLs are deterministically deduplicated (first
    occurrence wins).
    """
    _require(
        isinstance(capture_urls, (list, tuple)) and len(capture_urls) >= 1,
        "capture_urls must be a non-empty explicit allowlist",
    )
    declared = set(public)
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in capture_urls:
        _require(
            isinstance(raw, str) and raw.strip(),
            f"capture_url must be a non-empty string, got {raw!r}",
        )
        parts = urlsplit(raw)
        _require(
            parts.scheme in ("http", "https"),
            f"capture_url must be absolute http(s), got {raw!r}",
        )
        _require(bool(parts.hostname), f"capture_url must declare a hostname, got {raw!r}")
        _require(
            parts.hostname in declared,
            f"capture_url host {parts.hostname!r} not declared in domains.public, got {raw!r}",
        )
        canon = make_canonical_url(raw)
        _require(
            canon in observed,
            f"capture_url not observed in homepage_map, got {raw!r}",
        )
        if canon not in seen:
            seen.add(canon)
            ordered.append(canon)
    return ordered


# --------------------------------------------------------------------------- #
# Filter homepage map to captured observations only (no caller mutation)
# --------------------------------------------------------------------------- #


def _filter_homepage_map(
    homepage_map: Mapping[str, Any], captured: set[str]
) -> dict:
    filtered = deepcopy(homepage_map)
    hp = filtered.get("homepage")
    if isinstance(hp, dict):
        nav = hp.get("navigation_links") or []
        hp["navigation_links"] = [
            item for item in nav if make_canonical_url(item.get("url", "")) in captured
        ]
        att = hp.get("attachment_links") or []
        hp["attachment_links"] = [
            item for item in att if make_canonical_url(item.get("url", "")) in captured
        ]
    sm = filtered.get("sitemap")
    if isinstance(sm, dict):
        urls = sm.get("urls") or []
        urls = [item for item in urls if make_canonical_url(item.get("url", "")) in captured]
        sm["urls"] = urls
        sm["url_count"] = len(urls)
    return filtered


# --------------------------------------------------------------------------- #
# Site model (routes + documents)
# --------------------------------------------------------------------------- #


def _build_site_model(site_id: str, hp_url: str, docs: list[dict]) -> list[dict]:
    routes: list[dict] = [
        {
            "route_id": ROOT_ROUTE_ID,
            "document_id": None,
            "url": hp_url,
            "canonical_url": make_canonical_url(hp_url),
            "title": None,
            "category": None,
            "content_type": None,
            "source_types": None,
        }
    ]
    for doc in docs:
        num = doc["id"].split("-")[-1]
        routes.append(
            {
                "route_id": f"route-{num}",
                "document_id": doc["id"],
                "url": doc["url"],
                "canonical_url": doc["canonical_url"],
                "title": doc.get("title") or None,
                "category": doc.get("category"),
                "content_type": doc.get("content_type"),
                "source_types": doc.get("source_types"),
            }
        )
    return routes


# --------------------------------------------------------------------------- #
# Capability bindings (bind only what the candidate already declares)
# --------------------------------------------------------------------------- #


def _build_capability_bindings(
    candidate: Mapping[str, Any], routes: list[dict]
) -> list[dict]:
    url_to_route: dict[str, str] = {}
    for r in routes:
        if r["route_id"] == ROOT_ROUTE_ID:
            continue
        url_to_route[r["url"]] = r["route_id"]
        url_to_route[r["canonical_url"]] = r["route_id"]

    bindings: list[dict] = []
    for cap in candidate.get("capabilities") or []:
        cap_id = cap["id"]
        state = cap.get("state")
        if state in ("configured", "detected"):
            route_ids: list[str] = []
            for ev in cap.get("evidence_refs") or []:
                if isinstance(ev, str) and ev.startswith(("http://", "https://")):
                    rid = url_to_route.get(ev) or url_to_route.get(make_canonical_url(ev))
                    if rid and rid not in route_ids:
                        route_ids.append(rid)
            _require(
                len(route_ids) >= 1,
                f"detected capability {cap_id!r} evidence route not in captured model",
            )
            bindings.append(
                {
                    "capability_id": cap_id,
                    "candidate_state": state,
                    "binding_state": "bound",
                    "route_ids": route_ids,
                }
            )
        else:
            bindings.append(
                {
                    "capability_id": cap_id,
                    "candidate_state": state,
                    "binding_state": "review_required" if state == "review_required" else "unbound",
                    "route_ids": [],
                }
            )
    return bindings


# --------------------------------------------------------------------------- #
# Action graph (navigation-only planning artifact)
# --------------------------------------------------------------------------- #


def _build_action_graph(routes: list[dict]) -> dict:
    actions: list[dict] = []
    n = 1
    for r in routes:
        if r["route_id"] == ROOT_ROUTE_ID:
            continue
        actions.append(
            {
                "action_id": f"action-{n:06d}",
                "action_type": "navigate",
                "from_route_id": ROOT_ROUTE_ID,
                "to_route_id": r["route_id"],
                "safety_level": "navigate",
                "requires_user_confirmation": False,
            }
        )
        n += 1
    return {
        "mode": "offline_fixture",
        "action_type_allowed": "navigate",
        "actions": actions,
        "action_count": len(actions),
    }


# --------------------------------------------------------------------------- #
# QA manifest (derived, not decorative)
# --------------------------------------------------------------------------- #


def _build_qa_manifest(
    site_id: str,
    refs: list[str],
    public: list[str],
    routes: list[dict],
    docs: list[dict],
    actions: list[dict],
    bindings: list[dict],
    captured: set[str],
) -> dict:
    route_ids = {r["route_id"] for r in routes}
    declared = set(public)

    non_root_routes = [r for r in routes if r["route_id"] != ROOT_ROUTE_ID]

    all_routes_in_capture_scope = all(
        (r["url"] in captured or r["canonical_url"] in captured) for r in non_root_routes
    )
    all_routes_declared_domain = all(
        bool(urlsplit(r["url"]).hostname) and urlsplit(r["url"]).hostname in declared
        for r in routes
    )

    referenced: set[str] = set()
    for b in bindings:
        referenced.update(b["route_ids"])
    for a in actions:
        referenced.add(a["from_route_id"])
        referenced.add(a["to_route_id"])
    all_route_refs_resolve = referenced.issubset(route_ids)

    all_detected_capabilities_bound = all(
        b["binding_state"] == "bound" and len(b["route_ids"]) >= 1
        for b in bindings
        if b["candidate_state"] in ("configured", "detected")
    )

    action_graph_navigate_only = all(a["action_type"] == "navigate" for a in actions)
    provenance_complete = bool(refs)

    expected_route_ids = {f"route-{i:06d}" for i in range(1, len(docs) + 1)}
    actual_route_ids = {r["route_id"] for r in non_root_routes}
    deterministic_ids = actual_route_ids == expected_route_ids and all(
        d["id"] == f"doc-{i:06d}" for i, d in enumerate(docs, start=1)
    )

    bound_count = sum(1 for b in bindings if b["binding_state"] == "bound")
    review_count = sum(1 for b in bindings if b["candidate_state"] == "review_required")

    return {
        "site_id": site_id,
        "source_refs": list(refs),
        "route_count": len(routes),
        "document_count": len(docs),
        "action_count": len(actions),
        "bound_capability_count": bound_count,
        "review_required_capability_count": review_count,
        "checks": {
            "all_routes_in_capture_scope": bool(all_routes_in_capture_scope),
            "all_routes_declared_domain": bool(all_routes_declared_domain),
            "all_route_refs_resolve": bool(all_route_refs_resolve),
            "all_detected_capabilities_bound": bool(all_detected_capabilities_bound),
            "action_graph_navigate_only": bool(action_graph_navigate_only),
            "provenance_complete": bool(provenance_complete),
            "deterministic_ids": bool(deterministic_ids),
        },
        "offline_preview_input_ready": True,
        "production_ready": False,
        "production_promotion_requested": False,
        "actual_site_control_authorized": False,
        "live_network_authorized": False,
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def build_offline_site_model_bundle(
    candidate: Mapping[str, Any],
    homepage_map: Mapping[str, Any],
    *,
    homepage_map_source_ref: str,
    capture_urls: Sequence[str],
) -> dict:
    """Build a deterministic offline Site Model bundle from a pre-SiteSpec candidate.

    Pure function: no filesystem reads, no network, no provider, no time/random.
    ``homepage_map`` must be supplied pre-built (e.g. from
    ``HomepageMapper.extract_menu_links`` in test/construction code). ``capture_urls``
    is an explicit allowlist bounded to observed homepage-map URLs.
    """
    _require(isinstance(homepage_map, dict), "homepage_map must be a mapping")

    site_id, public, refs, hp_url = _validate_candidate(candidate, homepage_map_source_ref)
    observed = _observed_canon_set(homepage_map)
    captured = _validate_capture_urls(capture_urls, public, observed)

    filtered = _filter_homepage_map(homepage_map, set(captured))
    docs = DocumentIndexer().build_index(filtered)

    routes = _build_site_model(site_id, hp_url, docs)
    bindings = _build_capability_bindings(candidate, routes)
    action_graph = _build_action_graph(routes)
    qa = _build_qa_manifest(
        site_id, refs, public, routes, docs, action_graph["actions"], bindings, set(captured)
    )

    capture_plan = {
        "mode": "offline_fixture",
        "scope_kind": "explicit_url_set",
        "live_network_authorized": False,
        "root_url": hp_url,
        "allowed_domains": list(public),
        "captured_urls": list(captured),
        "url_count": len(captured),
        "source_refs": list(refs),
    }

    return {
        "bundle_version": BUNDLE_VERSION,
        "site_id": site_id,
        "provenance": {"source_refs": list(refs)},
        "capture_plan": capture_plan,
        "site_model": {
            "site_id": site_id,
            "root_route_id": ROOT_ROUTE_ID,
            "routes": routes,
            "documents": docs,
        },
        "capability_bindings": bindings,
        "action_graph": action_graph,
        "qa_manifest": qa,
    }
