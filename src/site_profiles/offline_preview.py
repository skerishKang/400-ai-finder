"""Offline generic structural preview renderer (#1232).

Pure deterministic renderer. No filesystem reads, no network, no provider, no
time/random, no site-specific branching.

Consumes an Offline Site Model bundle (the authoritative output of
``src.site_profiles.offline_site_model.build_offline_site_model_bundle``) and
produces a static, content-non-fabricating *structural* preview:

- one HTML page per Site Model route (``index.html`` for the root route,
  ``routes/<route_id>.html`` for every other route);
- a preview/provenance manifest.

It does NOT render a visual-fidelity or golden-parity preview; it renders only
the structure (route tree, navigation graph, document inventory, capability
state). All bundle-controlled strings are HTML-escaped. No JavaScript, no
inline handlers, no external assets, no fabricated content.
"""

from __future__ import annotations

import html
import re
from copy import deepcopy
from typing import Any, Mapping

PREVIEW_VERSION = "1.0.0"
SUPPORTED_BUNDLE_VERSION = "1.0.0"

OUTPUT_INDEX = "index.html"
ROUTES_DIR = "routes"

# Path-safe route id: lowercase alphanumeric + hyphen, must start alphanumeric.
ROUTE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Flag names as produced by the Site Model bundle (nested in qa_manifest).
_OFFLINE_PREVIEW_INPUT_READY = "offline_preview_input_ready"
_PRODUCTION_READY = "production_ready"
_PRODUCTION_PROMOTION_REQUESTED = "production_promotion_requested"
_ACTUAL_SITE_CONTROL_AUTHORIZED = "actual_site_control_authorized"
_LIVE_NETWORK_AUTHORIZED = "live_network_authorized"


class OfflinePreviewError(Exception):
    """Raised when an offline preview cannot be built fail-closed."""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise OfflinePreviewError(msg)


def _esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _qa_flag(bundle: Mapping[str, Any], name: str, *, default: Any = None) -> Any:
    """Resolve a qa_manifest flag, falling back to a top-level key."""
    qa = bundle.get("qa_manifest") if isinstance(bundle, dict) else None
    if isinstance(qa, dict) and qa.get(name) is not None:
        return qa.get(name)
    if isinstance(bundle, dict) and bundle.get(name) is not None:
        return bundle.get(name)
    return default


def _output_path(root_route_id: str, route_id: str) -> str:
    if route_id == root_route_id:
        return OUTPUT_INDEX
    return f"{ROUTES_DIR}/{route_id}.html"


# --------------------------------------------------------------------------- #
# Validation (fail-closed)
# --------------------------------------------------------------------------- #


def _validate(bundle: Mapping[str, Any]) -> tuple[dict, list, list, list, list]:
    _require(isinstance(bundle, dict), "bundle must be a mapping")

    bundle_version = bundle.get("bundle_version")
    _require(
        bundle_version == SUPPORTED_BUNDLE_VERSION,
        f"unsupported bundle_version: {bundle_version!r}",
    )

    site_id = bundle.get("site_id")
    _require(isinstance(site_id, str) and site_id, "site_id required and non-empty")

    _require(
        _qa_flag(bundle, _OFFLINE_PREVIEW_INPUT_READY) is True,
        "offline_preview_input_ready must be true",
    )
    _require(
        _qa_flag(bundle, _PRODUCTION_READY) is False,
        "production_ready must be false",
    )
    _require(
        _qa_flag(bundle, _PRODUCTION_PROMOTION_REQUESTED) is False,
        "production_promotion_requested must be false",
    )
    _require(
        _qa_flag(bundle, _ACTUAL_SITE_CONTROL_AUTHORIZED) is False,
        "actual_site_control_authorized must be false",
    )
    _require(
        _qa_flag(bundle, _LIVE_NETWORK_AUTHORIZED) is False,
        "live_network_authorized must be false",
    )

    site_model = bundle.get("site_model") or {}
    _require(isinstance(site_model, dict), "site_model required")
    root_route_id = site_model.get("root_route_id")
    routes = site_model.get("routes") or []
    documents = site_model.get("documents") or []
    _require(isinstance(routes, list) and len(routes) >= 1, "routes required")
    _require(isinstance(documents, list), "documents must be a list")

    seen_route: set[str] = set()
    for r in routes:
        rid = r.get("route_id") if isinstance(r, dict) else None
        _require(isinstance(rid, str) and rid, "route.route_id required")
        _require(ROUTE_ID_PATTERN.match(rid), f"route_id not path-safe: {rid!r}")
        _require(rid not in seen_route, f"duplicate route_id: {rid!r}")
        seen_route.add(rid)

    doc_ids: set[str] = set()
    for d in documents:
        did = d.get("id") if isinstance(d, dict) else None
        _require(isinstance(did, str) and did, "document.id required")
        _require(did not in doc_ids, f"duplicate document id: {did!r}")
        doc_ids.add(did)

    _require(
        root_route_id in seen_route,
        f"root_route_id not in routes: {root_route_id!r}",
    )

    for r in routes:
        did = r.get("document_id")
        if did is not None:
            _require(
                did in doc_ids,
                f"route {r.get('route_id')!r} refs missing document {did!r}",
            )

    action_graph = bundle.get("action_graph") or {}
    actions = action_graph.get("actions") or []
    _require(isinstance(actions, list), "action_graph.actions must be a list")
    for a in actions:
        atype = a.get("action_type") if isinstance(a, dict) else None
        _require(atype == "navigate", f"only navigate actions allowed, got {atype!r}")
        frid = a.get("from_route_id")
        trid = a.get("to_route_id")
        _require(frid in seen_route, f"action from_route_id unresolved: {frid!r}")
        _require(trid in seen_route, f"action to_route_id unresolved: {trid!r}")

    bindings = bundle.get("capability_bindings") or []
    _require(isinstance(bindings, list), "capability_bindings must be a list")
    for b in bindings:
        cid = b.get("capability_id") if isinstance(b, dict) else None
        _require(isinstance(cid, str) and cid, "capability_id required")
        for rid in b.get("route_ids") or []:
            _require(
                rid in seen_route,
                f"capability {cid!r} refs unresolved route {rid!r}",
            )
        cstate = b.get("candidate_state")
        bstate = b.get("binding_state")
        if cstate in ("configured", "detected"):
            _require(
                bstate == "bound",
                f"capability {cid!r} ({cstate}) must stay bound",
            )
        if cstate == "review_required":
            _require(
                bstate != "bound",
                f"review_required capability {cid!r} cannot be bound",
            )

    return site_model, routes, documents, actions, bindings


# --------------------------------------------------------------------------- #
# Rendering (deterministic, escaped, no script/external assets)
# --------------------------------------------------------------------------- #


def _render_header(site_id: str, source_refs: list) -> str:
    refs = "".join(f"<li>{_esc(r)}</li>" for r in (source_refs or []))
    return (
        "<header>"
        "<h1>Offline structural preview</h1>"
        f'<p class="site-id">{_esc(site_id)}</p>'
        '<details class="provenance">'
        "<summary>Provenance (offline fixture)</summary>"
        f"<ul>{refs}</ul>"
        "</details>"
        "</header>"
    )


def _render_footer() -> str:
    return (
        "<footer>"
        "<p>Generated offline structural preview. No live site control, "
        "no network, no fabricated content.</p>"
        "</footer>"
    )


def _render_nav(actions: list, route_by_id: dict) -> str:
    links = []
    for a in actions:
        target = a.get("to_route_id")
        rt = route_by_id.get(target) or {}
        text = rt.get("title") or target
        href = _output_path(route_by_id.get("_root_"), target)
        links.append(f'<li><a href="{_esc(href)}">{_esc(text)}</a></li>')
    return f"<nav><ul>{''.join(links)}</ul></nav>"


def _render_root_main(bindings: list) -> str:
    items = []
    for b in bindings:
        cid = _esc(b.get("capability_id"))
        cstate = _esc(b.get("candidate_state"))
        bstate = _esc(b.get("binding_state"))
        items.append(
            "<li>"
            f'<span class="capability-id">{cid}</span>'
            f'<span class="candidate-state">{cstate}</span>'
            f'<span class="binding-state">{bstate}</span>'
            "</li>"
        )
    return (
        "<main>"
        "<h2>Capability state</h2>"
        f'<ul class="capabilities">{"" .join(items)}</ul>'
        "</main>"
    )


def _render_document_main(route: dict) -> str:
    parts = []
    title = route.get("title")
    if title is not None:
        parts.append(f"<h2>{_esc(title)}</h2>")

    rows = []
    for key in ("document_id", "category", "content_type"):
        val = route.get(key)
        if val is not None:
            rows.append(f"<dt>{_esc(key)}</dt><dd>{_esc(val)}</dd>")
    st = route.get("source_types")
    if st is not None:
        if isinstance(st, list):
            rendered = ", ".join(_esc(s) for s in st)
        else:
            rendered = _esc(st)
        rows.append(f"<dt>source_types</dt><dd>{rendered}</dd>")

    dl = f'<dl class="route-metadata">{"" .join(rows)}</dl>' if rows else ""
    return f"<main>{parts[0] if parts else ''}{dl}</main>"


def _render_page(
    *,
    site_id: str,
    source_refs: list,
    body: str,
    nav: str | None = None,
) -> str:
    head = (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_esc(site_id)} — offline structural preview</title>"
        "</head>"
        "<body>"
    )
    tail = "</body></html>"
    nav_block = nav if nav is not None else ""
    return head + _render_header(site_id, source_refs) + nav_block + body + _render_footer() + tail


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def build_offline_preview(bundle: Mapping[str, Any]) -> dict:
    """Build a deterministic static structural preview from a Site Model bundle.

    Returns ``{"manifest": <preview/provenance manifest>, "pages": <path -> html>}``.
    Pure function: no filesystem, no network, no provider, no time/random.
    """
    bundle = deepcopy(bundle)
    site_model, routes, _documents, actions, bindings = _validate(bundle)

    site_id = bundle["site_id"]
    root_route_id = site_model["root_route_id"]
    route_by_id = {r["route_id"]: r for r in routes}
    route_by_id["_root_"] = root_route_id

    source_refs = list(
        ((bundle.get("provenance") or {}).get("source_refs") or [])
    )

    pages: dict[str, str] = {}
    route_entries = []
    for r in routes:
        rid = r["route_id"]
        out = _output_path(root_route_id, rid)
        route_entries.append({"route_id": rid, "output_path": out})
        if rid == root_route_id:
            body = _render_root_main(bindings)
            nav = _render_nav(actions, route_by_id) if actions else None
            pages[out] = _render_page(
                site_id=site_id, source_refs=source_refs, body=body, nav=nav
            )
        else:
            body = _render_document_main(r)
            pages[out] = _render_page(
                site_id=site_id, source_refs=source_refs, body=body
            )

    manifest = {
        "preview_version": PREVIEW_VERSION,
        "site_id": site_id,
        "root_output_path": OUTPUT_INDEX,
        "routes": route_entries,
        "route_count": len(routes),
        "action_count": len(actions),
        "capability_bindings": [
            {
                "capability_id": b.get("capability_id"),
                "candidate_state": b.get("candidate_state"),
                "binding_state": b.get("binding_state"),
                "route_ids": list(b.get("route_ids") or []),
            }
            for b in bindings
        ],
        "provenance": {"source_refs": source_refs},
        "assets": [],
        "external_assets": [],
        "offline_only": True,
        "live_network_authorized": False,
        "actual_site_control_authorized": False,
        "production_ready": False,
        "production_promotion_requested": False,
        "visual_parity_claimed": False,
    }

    return {"manifest": manifest, "pages": pages}
