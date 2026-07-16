"""Project canonical home clone fixture into a browser-safe static JS artifact.

Offline, deterministic, network-free. Mirrors the official-snapshot generator
pattern used by scripts/generate_bukgu_official_snapshots.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))
# Drop a foreign ``src`` package if the process PYTHONPATH points elsewhere.
_foreign = sys.modules.get("src")
if _foreign is not None:
    _file = getattr(_foreign, "__file__", "") or ""
    _paths = list(getattr(_foreign, "__path__", []) or [])
    _owned = _file.startswith(str(ROOT)) or any(p.startswith(str(ROOT)) for p in _paths)
    if not _owned:
        for _key in list(sys.modules):
            if _key == "src" or _key.startswith("src."):
                del sys.modules[_key]

CANONICAL_FIXTURE = (
    ROOT / "data" / "official_clone_fixtures" / "bukgu_gwangju" / "home.json"
)
BROWSER_TARGET = ROOT / "src" / "web" / "static" / "bukgu-home-clone-fixture.js"

GENERATOR_ID = "scripts/generate_bukgu_home_clone_fixture.py"
GENERATOR_VERSION = "1.0.0"
GLOBAL_NAME = "__BUKGU_HOME_CLONE_FIXTURE__"

REQUIRED_REGION_IDS = (
    "utility_navigation",
    "main_banner",
    "resident_service_shortcuts",
    "notice_news",
    "related_site_controls",
    "footer_identity_contact",
)

REQUIRED_REGION_STATUS = "fixture-ready-renderer-not-wired"

ITEM_FIELD_KEYS = (
    "item_id",
    "order",
    "text",
    "date_text",
    "href",
    "resolved_url",
    "same_origin",
    "dom_order",
    "group",
    "group_order",
    "asset_url",
    "local_variant",
    "effective_variant",
    "variant",
    "visibility",
    "title_attr",
    "target",
    "kind",
)

# Closed Page Agent / canvas action target mappings.
# Only exact label + exact href evidence from the committed fixture is allowed.
# Prefer region_item when present; otherwise navigation inventory.
ACTION_TARGET_RULES: tuple[dict[str, str], ...] = (
    {
        "action_target": "nav-civil-service",
        "prefer": "navigation",
        "text": "종합민원",
        "href": "/menu.es?mid=a10101000000",
    },
    {
        "action_target": "nav-complaint-board",
        "prefer": "navigation",
        "text": "소통광장",
        "href": "/menu.es?mid=a10201000000",
    },
    {
        "action_target": "nav-apartment-dept",
        "prefer": "navigation",
        "text": "행정조직도",
        "href": "/menu.es?mid=a10602010000",
    },
    {
        "action_target": "nav-passport-guidance",
        "prefer": "navigation",
        "text": "여권 발급",
        "href": "/menu.es?mid=a10101060200",
    },
    {
        "action_target": "nav-bulky-waste-disposal",
        "prefer": "region_item",
        "text": "대형폐기물",
        "href": "/menu.es?mid=a10406070000",
    },
    {
        "action_target": "mayor-office-open",
        "prefer": "navigation",
        "text": "열린구청장실바로가기",
        "href": "/mayor/",
    },
)


class ProjectionError(ValueError):
    """Raised when the canonical fixture fails projection validation."""


def fixture_body_checksum(fixture: Mapping[str, Any]) -> str:
    """Checksum over fixture excluding the self-describing fixture_sha256 field."""
    body = {k: v for k, v in fixture.items() if k != "fixture_sha256"}
    payload = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _pretty_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)


def _project_present(source: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in keys:
        if key not in source:
            continue
        value = source[key]
        if value is None:
            continue
        out[key] = value
    return out


def _project_item(item: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise ProjectionError("region item must be an object")
    projected = _project_present(item, ITEM_FIELD_KEYS)
    if "item_id" not in projected or "order" not in projected:
        raise ProjectionError("region item missing item_id/order")
    return projected


def _project_source_evidence(evidence: Any) -> dict[str, Any] | None:
    if not isinstance(evidence, Mapping):
        return None
    keys = (
        "tag",
        "id",
        "classes",
        "ancestor_path",
        "source_order",
        "occurrence_count",
        "local_variant",
        "effective_variant",
        "variant",
        "fragment_sha256",
        "hash_rule",
        "kind",
        "order",
        "class",
    )
    return _project_present(evidence, keys) or None


def _project_region(region: Mapping[str, Any]) -> dict[str, Any]:
    region_id = region.get("region_id")
    if not isinstance(region_id, str) or not region_id:
        raise ProjectionError("region missing region_id")
    status = region.get("status")
    if status != REQUIRED_REGION_STATUS:
        raise ProjectionError(
            f"region {region_id} status must be {REQUIRED_REGION_STATUS!r}, got {status!r}"
        )
    items_raw = region.get("items")
    if not isinstance(items_raw, list):
        raise ProjectionError(f"region {region_id} items must be a list")

    items = [_project_item(item) for item in items_raw]
    seen_ids: set[str] = set()
    prev_order = 0
    for item in items:
        item_id = item["item_id"]
        if item_id in seen_ids:
            raise ProjectionError(f"duplicate item_id in {region_id}: {item_id}")
        seen_ids.add(item_id)
        order = item["order"]
        if not isinstance(order, int) or order <= prev_order:
            raise ProjectionError(
                f"invalid order sequence in {region_id}: {order} after {prev_order}"
            )
        prev_order = order

    projected: dict[str, Any] = {
        "region_id": region_id,
        "status": status,
        "item_count": len(items),
        "items": items,
    }
    if "candidate_count" in region and region["candidate_count"] is not None:
        projected["candidate_count"] = region["candidate_count"]
    evidence = _project_source_evidence(region.get("source_evidence"))
    if evidence is not None:
        projected["source_evidence"] = evidence
    if isinstance(region.get("variant_counts"), Mapping):
        projected["variant_counts"] = dict(region["variant_counts"])
    if isinstance(region.get("groups"), list):
        projected["groups"] = region["groups"]
    if isinstance(region.get("controls"), list):
        projected["controls"] = region["controls"]
    if region.get("heading") is not None:
        projected["heading"] = region["heading"]

    claimed_count = region.get("item_count")
    if isinstance(claimed_count, int) and claimed_count != len(items):
        raise ProjectionError(
            f"region {region_id} item_count mismatch: claimed {claimed_count}, got {len(items)}"
        )
    return projected


def _find_region_item_match(
    regions: Mapping[str, Mapping[str, Any]], text: str, href: str
) -> dict[str, Any] | None:
    for region_id in REQUIRED_REGION_IDS:
        region = regions[region_id]
        for item in region["items"]:
            if item.get("text") == text and item.get("href") == href:
                return {
                    "source": "region_item",
                    "region_id": region_id,
                    "item_id": item["item_id"],
                    "text": text,
                    "href": href,
                    "same_origin": item.get("same_origin"),
                    "resolved_url": item.get("resolved_url"),
                }
    return None


def _find_navigation_match(
    navigation: list[Mapping[str, Any]], text: str, href: str
) -> dict[str, Any] | None:
    for item in navigation:
        if not isinstance(item, Mapping):
            continue
        if item.get("label") == text and item.get("href") == href:
            return {
                "source": "navigation",
                "nav_item_id": item.get("item_id"),
                "text": text,
                "href": href,
                "same_origin": item.get("same_origin"),
                "resolved_url": item.get("resolved_url") or item.get("source_url"),
            }
    return None


def _build_action_target_mappings(
    regions: Mapping[str, Mapping[str, Any]],
    navigation: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for rule in ACTION_TARGET_RULES:
        text = rule["text"]
        href = rule["href"]
        prefer = rule["prefer"]
        match: dict[str, Any] | None = None
        if prefer == "region_item":
            match = _find_region_item_match(regions, text, href)
            if match is None:
                match = _find_navigation_match(navigation, text, href)
        else:
            match = _find_navigation_match(navigation, text, href)
            if match is None:
                match = _find_region_item_match(regions, text, href)
        if match is None:
            raise ProjectionError(
                f"action target {rule['action_target']} has no exact "
                f"label/href evidence: {text!r} {href!r}"
            )
        mappings.append(
            {
                "action_target": rule["action_target"],
                "evidence_rule": "exact_label_and_href",
                **match,
            }
        )
    return mappings


def load_and_validate_fixture() -> dict[str, Any]:
    if not CANONICAL_FIXTURE.is_file():
        raise ProjectionError(f"missing canonical fixture: {CANONICAL_FIXTURE}")
    raw = CANONICAL_FIXTURE.read_text(encoding="utf-8")
    fixture = json.loads(raw)
    if not isinstance(fixture, dict):
        raise ProjectionError("fixture root must be an object")

    if fixture.get("schema_version") != 1:
        raise ProjectionError("schema_version must be 1")
    if fixture.get("fixture_kind") != "official_home_clone_fixture":
        raise ProjectionError("fixture_kind must be official_home_clone_fixture")
    if fixture.get("route_id") != "home":
        raise ProjectionError("route_id must be home")
    if fixture.get("clone_status") != "capture_required":
        raise ProjectionError("clone_status must remain capture_required")

    boundaries = fixture.get("boundaries")
    if not isinstance(boundaries, Mapping):
        raise ProjectionError("boundaries missing")
    if boundaries.get("exact_clone_claimed") is not False:
        raise ProjectionError("exact_clone_claimed must be false")
    if boundaries.get("home_remains_capture_required") is not True:
        raise ProjectionError("home_remains_capture_required must be true")

    claimed_sha = fixture.get("fixture_sha256")
    if not isinstance(claimed_sha, str) or len(claimed_sha) != 64:
        raise ProjectionError("fixture_sha256 missing or invalid")
    actual_sha = fixture_body_checksum(fixture)
    if claimed_sha != actual_sha:
        raise ProjectionError(
            f"fixture_sha256 mismatch: claimed={claimed_sha} actual={actual_sha}"
        )

    regions_raw = fixture.get("regions")
    if not isinstance(regions_raw, list):
        raise ProjectionError("regions must be a list")
    by_id = {
        r["region_id"]: r
        for r in regions_raw
        if isinstance(r, Mapping) and isinstance(r.get("region_id"), str)
    }
    for region_id in REQUIRED_REGION_IDS:
        if region_id not in by_id:
            raise ProjectionError(f"missing required region: {region_id}")

    navigation = fixture.get("navigation")
    if not isinstance(navigation, list):
        raise ProjectionError("navigation must be a list")

    return fixture


def build_projection(fixture: Mapping[str, Any] | None = None) -> dict[str, Any]:
    fixture = fixture if fixture is not None else load_and_validate_fixture()
    source = fixture["source_identity"]
    if not isinstance(source, Mapping):
        raise ProjectionError("source_identity missing")

    regions_raw = {
        r["region_id"]: r
        for r in fixture["regions"]
        if isinstance(r, Mapping) and r.get("region_id") in REQUIRED_REGION_IDS
    }
    regions = {
        rid: _project_region(regions_raw[rid]) for rid in REQUIRED_REGION_IDS
    }
    navigation = fixture["navigation"]
    assert isinstance(navigation, list)
    mappings = _build_action_target_mappings(regions, navigation)

    html_seg = fixture.get("html_region_segmentation")
    parser_id = None
    parser_version = None
    if isinstance(html_seg, Mapping):
        parser_id = html_seg.get("parser_id")
        parser_version = html_seg.get("parser_version")

    projection: dict[str, Any] = {
        "schema_version": fixture["schema_version"],
        "fixture_kind": fixture["fixture_kind"],
        "fixture_id": fixture["fixture_id"],
        "route_id": fixture["route_id"],
        "site_id": fixture["site_id"],
        "clone_status": fixture["clone_status"],
        "exact_clone_claimed": False,
        "source": {
            "requested_url": source.get("requested_url"),
            "final_url": source.get("final_url"),
            "captured_at": source.get("captured_at"),
            "raw_capture_sha256": source.get("raw_capture_sha256"),
            "title": source.get("title"),
        },
        "fixture_sha256": fixture["fixture_sha256"],
        "generator": {
            "fixture_generator_id": source.get("generator_id"),
            "fixture_generator_version": source.get("generator_version"),
            "projection_generator_id": GENERATOR_ID,
            "projection_generator_version": GENERATOR_VERSION,
            "parser_id": parser_id,
            "parser_version": parser_version,
        },
        "region_order": list(REQUIRED_REGION_IDS),
        "regions": {rid: regions[rid] for rid in REQUIRED_REGION_IDS},
        "action_target_mappings": mappings,
        "counts": {
            "regions": len(REQUIRED_REGION_IDS),
            "items_by_region": {
                rid: regions[rid]["item_count"] for rid in REQUIRED_REGION_IDS
            },
            "variant_counts_by_region": {
                rid: regions[rid].get("variant_counts") for rid in REQUIRED_REGION_IDS
            },
            "assets_unresolved": (fixture.get("counts") or {}).get(
                "assets_unresolved", 174
            ),
        },
        "boundaries": {
            "network_at_generation": 0,
            "official_site_access": 0,
            "provider_api": 0,
            "firecrawl": 0,
            "ui_renderer_wired": True,
            "exact_clone_claimed": False,
            "home_remains_capture_required": True,
            "runtime_fetch": False,
            "remote_asset_src": False,
        },
    }
    return projection


def render_browser_artifact(projection: Mapping[str, Any] | None = None) -> str:
    projection = projection if projection is not None else build_projection()
    return (
        f"// AUTO-GENERATED by {GENERATOR_ID}.\n"
        "// Canonical source: data/official_clone_fixtures/bukgu_gwangju/home.json\n"
        "// Do not edit this file directly.\n"
        "(function (root) {\n"
        '  "use strict";\n'
        f"  root.{GLOBAL_NAME} = "
        + _pretty_json(projection)
        + ";\n"
        "})(typeof window !== \"undefined\" ? window : globalThis);\n"
    )


def expected_artifacts() -> dict[Path, str]:
    return {BROWSER_TARGET: render_browser_artifact()}


def check_generated_artifacts() -> list[Path]:
    stale: list[Path] = []
    for path, expected in expected_artifacts().items():
        try:
            actual = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            actual = ""
        if actual != expected:
            stale.append(path)
    return stale


def write_generated_artifacts() -> None:
    for path, content in expected_artifacts().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"[home-clone-fixture] wrote {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when committed generated artifacts do not match canonical fixture projection",
    )
    args = parser.parse_args()
    try:
        if args.check:
            stale = check_generated_artifacts()
            if stale:
                for path in stale:
                    print(f"[home-clone-fixture] stale: {path.relative_to(ROOT)}")
                return 1
            print("[home-clone-fixture] generated artifacts are current")
            return 0
        write_generated_artifacts()
        return 0
    except ProjectionError as exc:
        print(f"[home-clone-fixture] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
