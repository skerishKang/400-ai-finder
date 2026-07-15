#!/usr/bin/env python3
"""Build the canonical offline home clone fixture from committed #1160 captures.

Source of truth remains the committed capture inventory under
data/official_captures/bukgu_gwangju/home/. This script promotes that inventory
into a structured clone fixture without network access.

Usage:
  python scripts/build_official_home_clone_fixture.py
  python scripts/build_official_home_clone_fixture.py --check

No wall-clock timestamps are read. Capture metadata supplies captured_at.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOME_CAPTURE_DIR = ROOT / "data" / "official_captures" / "bukgu_gwangju" / "home"
RAW_PATH = HOME_CAPTURE_DIR / "raw-homepage.html"
META_PATH = HOME_CAPTURE_DIR / "capture-metadata.json"
NAV_PATH = HOME_CAPTURE_DIR / "navigation-inventory.json"
ASSET_PATH = HOME_CAPTURE_DIR / "asset-inventory.json"
NOTES_PATH = HOME_CAPTURE_DIR / "CAPTURE-NOTES.md"

FIXTURE_PATH = (
    ROOT / "data" / "official_clone_fixtures" / "bukgu_gwangju" / "home.json"
)

GENERATOR_ID = "scripts/build_official_home_clone_fixture.py"
GENERATOR_VERSION = "1.0.0"
SCHEMA_VERSION = 1
FIXTURE_KIND = "official_home_clone_fixture"
APPROVED_HOST = "bukgu.gwangju.kr"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Regions the clone plan expects. Only mark ready when capture evidence exists.
EXPECTED_REGION_SPECS: tuple[dict[str, str], ...] = (
    {
        "region_id": "government_notice",
        "label": "government notice",
        "evidence_mode": "nav_label_prefix",
        "evidence_value": "이 누리집은 대한민국 공식 전자정부 누리집입니다.",
    },
    {
        "region_id": "site_identity_logo",
        "label": "site identity/logo",
        "evidence_mode": "nav_order",
        "evidence_value": "3",
    },
    {
        "region_id": "utility_navigation",
        "label": "utility navigation",
        "evidence_mode": "unresolved",
        "evidence_value": "no deterministic source boundary distinct from global header nav",
    },
    {
        "region_id": "global_navigation",
        "label": "global navigation",
        "evidence_mode": "section",
        "evidence_value": "header",
    },
    {
        "region_id": "main_banner",
        "label": "main/banner regions",
        "evidence_mode": "unresolved",
        "evidence_value": "no deterministic source boundary in capture hierarchy",
    },
    {
        "region_id": "resident_service_shortcuts",
        "label": "resident service shortcuts",
        "evidence_mode": "unresolved",
        "evidence_value": "no deterministic source boundary in capture hierarchy",
    },
    {
        "region_id": "notice_news",
        "label": "notice/news regions",
        "evidence_mode": "unresolved",
        "evidence_value": "no deterministic source boundary in capture hierarchy",
    },
    {
        "region_id": "related_site_controls",
        "label": "related-site controls",
        "evidence_mode": "unresolved",
        "evidence_value": "no deterministic source boundary in capture hierarchy",
    },
    {
        "region_id": "footer_navigation",
        "label": "footer navigation",
        "evidence_mode": "section",
        "evidence_value": "footer",
    },
    {
        "region_id": "footer_identity_contact",
        "label": "footer identity/contact/copyright regions",
        "evidence_mode": "unresolved",
        "evidence_value": "footer section captured as links only; identity/contact blocks not separately bounded",
    },
    {
        "region_id": "document_skip_and_misc",
        "label": "document-level skip/misc navigation",
        "evidence_mode": "section",
        "evidence_value": "document",
    },
)


class FixtureBuildError(ValueError):
    """Raised when capture inputs or generated fixture fail integrity checks."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FixtureBuildError(f"missing required capture file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FixtureBuildError(f"invalid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise FixtureBuildError(f"JSON root must be object: {path}")
    return data


def metadata_checksum(meta: Mapping[str, Any]) -> str:
    """Match scripts/capture_official_home_inventory.metadata_checksum."""
    body = {k: v for k, v in meta.items() if k != "metadata_sha256"}
    payload = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stable_dump(obj: Any) -> str:
    """Stable pretty JSON with trailing newline (committed fixture form)."""
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def fixture_body_checksum(fixture: Mapping[str, Any]) -> str:
    """Checksum over fixture excluding the self-describing fixture_sha256 field."""
    body = {k: v for k, v in fixture.items() if k != "fixture_sha256"}
    payload = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def is_approved_bukgu_url(value: object) -> bool:
    """Exact official-origin validation for home source identity URLs.

    Policy (no startswith host trust):
      - absolute URL only
      - scheme exactly https
      - hostname exactly bukgu.gwangju.kr
      - username/password absent
      - port absent or 443
      - malformed authority / non-string / blank → False
    """
    if not isinstance(value, str) or not value.strip():
        return False
    # Scheme-relative and non-http(s) schemes are never approved origins.
    if value.startswith("//") or "://" not in value:
        return False
    try:
        parts = urlsplit(value)
    except Exception:
        return False
    try:
        # Accessing .port may raise ValueError for malformed ports.
        port = parts.port
    except ValueError:
        return False
    if parts.scheme.lower() != "https":
        return False
    if parts.username is not None or parts.password is not None:
        return False
    # Require absolute authority (hostname present); bare paths rejected.
    host = (parts.hostname or "").lower()
    if host != APPROVED_HOST:
        return False
    if not parts.netloc:
        return False
    if port not in (None, 443):
        return False
    return True


def require_approved_bukgu_url(value: object, label: str) -> str:
    """Return the URL string or raise FixtureBuildError (never raw ValueError)."""
    if not is_approved_bukgu_url(value):
        raise FixtureBuildError(
            f"{label} must be an exact approved Buk-gu HTTPS origin URL"
        )
    return str(value)


def verify_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], bytes]:
    for path in (RAW_PATH, META_PATH, NAV_PATH, ASSET_PATH, NOTES_PATH):
        if not path.is_file():
            raise FixtureBuildError(f"missing required capture file: {path}")

    raw = RAW_PATH.read_bytes()
    meta = load_json(META_PATH)
    nav = load_json(NAV_PATH)
    assets = load_json(ASSET_PATH)

    if meta.get("route_id") != "home":
        raise FixtureBuildError("capture metadata route_id must be home")
    if meta.get("inventory_kind") != "official_home_source_inventory":
        raise FixtureBuildError("unexpected inventory_kind")
    if meta.get("status") != "capture_only":
        raise FixtureBuildError("capture status must remain capture_only for this slice")

    source = meta.get("source")
    if not isinstance(source, Mapping):
        raise FixtureBuildError("metadata.source must be an object")

    # Each source identity URL is validated independently (no compensation).
    require_approved_bukgu_url(source.get("requested_url"), "source.requested_url")
    require_approved_bukgu_url(
        source.get("final_resolved_url"), "source.final_resolved_url"
    )
    raw_sha = sha256_bytes(raw)
    claimed_raw = source.get("raw_content_sha256")
    if raw_sha != claimed_raw:
        raise FixtureBuildError(
            f"raw capture SHA-256 mismatch: file={raw_sha} metadata={claimed_raw}"
        )
    if len(raw) != source.get("raw_byte_length"):
        raise FixtureBuildError("raw byte length does not match metadata")

    claimed_meta = meta.get("metadata_sha256")
    computed_meta = metadata_checksum(meta)
    if claimed_meta != computed_meta:
        raise FixtureBuildError(
            f"metadata SHA-256 mismatch: claimed={claimed_meta} computed={computed_meta}"
        )
    if not SHA256_RE.fullmatch(str(claimed_meta or "")):
        raise FixtureBuildError("metadata_sha256 must be lowercase hex sha256")

    if nav.get("route_id") != "home" or assets.get("route_id") != "home":
        raise FixtureBuildError("navigation/asset inventories must declare route_id=home")

    if nav.get("item_count") != len(nav.get("items") or []):
        raise FixtureBuildError("navigation item_count mismatch")
    if assets.get("item_count") != len(assets.get("items") or []):
        raise FixtureBuildError("asset item_count mismatch")

    return meta, nav, assets, raw


def index_local_files_by_full_sha256() -> dict[str, list[str]]:
    """Map full-file SHA-256 → relative repo paths under src/web/static."""
    root = ROOT / "src" / "web" / "static"
    index: dict[str, list[str]] = {}
    if not root.is_dir():
        return index
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        digest = sha256_bytes(path.read_bytes())
        rel = path.relative_to(ROOT).as_posix()
        index.setdefault(digest, []).append(rel)
    return index


def is_full_file_hash(item: Mapping[str, Any]) -> bool:
    """Partial first-N-byte hashes are not full-file identity."""
    scope = item.get("hash_scope")
    size = item.get("size_bytes")
    hashed = item.get("hashed_byte_count")
    digest = item.get("sha256")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        return False
    if scope is None:
        return False
    if scope == "full_file":
        return True
    # Capture used first_65536_bytes; only treat as full identity when entire
    # response fit inside that window (hashed_byte_count == size_bytes).
    if scope == "first_65536_bytes" and isinstance(size, int) and isinstance(hashed, int):
        return size == hashed and size > 0
    return False


def build_navigation_items(nav: Mapping[str, Any]) -> list[dict[str, Any]]:
    items_out: list[dict[str, Any]] = []
    for item in nav["items"]:
        order = item["order"]
        label = item.get("visible_label")
        label_source = item.get("label_source")
        absence = item.get("label_absence_reason")
        # Preserve blank labels exactly as capture recorded them.
        nav_item = {
            "item_id": f"nav-{int(order):04d}",
            "order": order,
            "label": label if label is not None else "",
            "label_source": label_source,
            "label_absence_reason": absence,
            "href": item.get("source_url"),
            "source_url": item.get("source_url"),
            "resolved_url": item.get("resolved_url"),
            "same_origin": item.get("same_origin"),
            "ancestor_hierarchy": list(item.get("ancestor_sections") or []),
            "depth": item.get("hierarchy_depth"),
            "dom_order": order,
            "region_identity": item.get("section"),
            "link_type": item.get("link_type"),
            "title_attr": item.get("title_attr") or "",
            "target": item.get("target") or "",
            "capture_result": item.get("capture_result"),
        }
        items_out.append(nav_item)
    # Preserve capture order; do not re-sort labels.
    orders = [i["order"] for i in items_out]
    if orders != list(range(1, len(orders) + 1)):
        raise FixtureBuildError("navigation DOM order must be contiguous 1..N")
    ids = [i["item_id"] for i in items_out]
    if len(ids) != len(set(ids)):
        raise FixtureBuildError("duplicate navigation item_id values")
    return items_out


def build_assets(
    assets: Mapping[str, Any], local_index: Mapping[str, list[str]]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, item in enumerate(assets["items"], start=1):
        digest = item.get("sha256")
        full = is_full_file_hash(item)
        local_paths: list[str] = []
        local_availability = "unresolved"
        identity_evidence: list[str] = []
        unresolved_reason = None
        local_candidate_path = None
        status = "unresolved-asset"

        if full and isinstance(digest, str) and digest in local_index:
            local_paths = list(local_index[digest])
            local_candidate_path = local_paths[0]
            local_availability = "ready-with-existing-local-asset"
            identity_evidence = [
                "matching_full_file_sha256",
                f"inventory_sha256={digest}",
                f"local_path={local_candidate_path}",
            ]
            status = "ready-with-existing-local-asset"
        else:
            if digest and item.get("hash_scope") == "first_65536_bytes" and not full:
                unresolved_reason = (
                    "partial hash is not treated as full-file identity"
                )
            elif item.get("capture_result") == "listed_unprobed":
                unresolved_reason = "asset listed in capture without body hash probe"
            elif not digest:
                unresolved_reason = "no inventory checksum available"
            else:
                unresolved_reason = (
                    "no exact local asset identity evidence "
                    "(checksum/source-url mapping/documented exact identity)"
                )
            local_availability = "unresolved"

        out.append(
            {
                "asset_id": f"asset-{index:04d}",
                "order": index,
                "source_url": item.get("source_url"),
                "requested_url": item.get("requested_url"),
                "resolved_url": item.get("resolved_url"),
                "type": item.get("asset_type"),
                "same_origin": item.get("same_origin"),
                "captured_inventory_identity": {
                    "order": index,
                    "section": item.get("section"),
                    "tag": item.get("tag"),
                    "capture_result": item.get("capture_result"),
                    "response_status": item.get("response_status"),
                    "content_type": item.get("content_type"),
                    "size_bytes": item.get("size_bytes"),
                },
                "local_availability": local_availability,
                "local_candidate_path": local_candidate_path,
                "local_candidate_paths": local_paths,
                "hash_scope": item.get("hash_scope"),
                "inventory_sha256": digest,
                "hashed_byte_count": item.get("hashed_byte_count"),
                "identity_evidence": identity_evidence,
                "status": status,
                "unresolved_reason": unresolved_reason,
            }
        )
    ids = [a["asset_id"] for a in out]
    if len(ids) != len(set(ids)):
        raise FixtureBuildError("duplicate asset_id values")
    return out


def build_regions(
    nav: Mapping[str, Any], navigation_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    hierarchy = list(nav.get("hierarchy") or [])
    hierarchy_order = {
        node.get("section"): node.get("order") for node in hierarchy if isinstance(node, dict)
    }

    by_section: dict[str, list[str]] = {}
    for item in navigation_items:
        section = item.get("region_identity") or "document"
        by_section.setdefault(str(section), []).append(item["item_id"])

    regions: list[dict[str, Any]] = []
    # First emit hierarchy nodes in capture order (header then footer).
    for node in hierarchy:
        section = node.get("section")
        regions.append(
            {
                "region_id": f"hierarchy_{section}",
                "label": f"capture hierarchy:{section}",
                "status": "ready" if by_section.get(str(section)) else "unresolved",
                "source_evidence": {
                    "kind": "navigation_hierarchy",
                    "tag": node.get("tag"),
                    "id": node.get("id"),
                    "class": node.get("class"),
                    "order": node.get("order"),
                },
                "dom_order": node.get("order"),
                "navigation_item_ids": list(by_section.get(str(section), [])),
                "reason": None
                if by_section.get(str(section))
                else "hierarchy node present without navigation items",
            }
        )

    # Then emit plan regions with explicit readiness / unresolved markers.
    for spec in EXPECTED_REGION_SPECS:
        mode = spec["evidence_mode"]
        value = spec["evidence_value"]
        region: dict[str, Any] = {
            "region_id": spec["region_id"],
            "label": spec["label"],
            "status": "unresolved",
            "source_evidence": None,
            "dom_order": None,
            "navigation_item_ids": [],
            "reason": None,
        }
        if mode == "unresolved":
            region["status"] = "unresolved"
            region["reason"] = value
            region["source_evidence"] = {
                "status": "unresolved",
                "reason": value,
            }
        elif mode == "section":
            ids = list(by_section.get(value, []))
            region["navigation_item_ids"] = ids
            region["dom_order"] = hierarchy_order.get(value)
            region["source_evidence"] = {
                "kind": "navigation_section",
                "section": value,
                "item_count": len(ids),
            }
            if ids:
                region["status"] = "fixture-ready-renderer-not-wired"
                region["reason"] = None
            else:
                region["status"] = "unresolved"
                region["reason"] = f"no navigation items in section {value}"
        elif mode == "nav_order":
            order = int(value)
            match = next((n for n in navigation_items if n["order"] == order), None)
            if match:
                region["status"] = "fixture-ready-renderer-not-wired"
                region["navigation_item_ids"] = [match["item_id"]]
                region["dom_order"] = order
                region["source_evidence"] = {
                    "kind": "navigation_item",
                    "item_id": match["item_id"],
                    "label": match["label"],
                    "label_source": match["label_source"],
                }
            else:
                region["status"] = "unresolved"
                region["reason"] = f"navigation order {order} missing"
        elif mode == "nav_label_prefix":
            matches = [
                n
                for n in navigation_items
                if isinstance(n.get("label"), str) and n["label"].startswith(value)
            ]
            if matches:
                region["status"] = "fixture-ready-renderer-not-wired"
                region["navigation_item_ids"] = [m["item_id"] for m in matches]
                region["dom_order"] = matches[0]["order"]
                region["source_evidence"] = {
                    "kind": "navigation_label_prefix",
                    "prefix": value,
                    "matched_item_ids": [m["item_id"] for m in matches],
                }
            else:
                region["status"] = "unresolved"
                region["reason"] = "label prefix not found in capture navigation"
        regions.append(region)

    region_ids = [r["region_id"] for r in regions]
    if len(region_ids) != len(set(region_ids)):
        raise FixtureBuildError("duplicate region_id values")
    return regions


def build_fixture() -> dict[str, Any]:
    meta, nav, assets, raw = verify_inputs()
    source = meta["source"]
    local_index = index_local_files_by_full_sha256()
    navigation_items = build_navigation_items(nav)
    asset_items = build_assets(assets, local_index)
    regions = build_regions(nav, navigation_items)

    ready_assets = sum(1 for a in asset_items if a["status"] == "ready-with-existing-local-asset")
    unresolved_assets = sum(1 for a in asset_items if a["status"] == "unresolved-asset")
    ready_regions = sum(
        1
        for r in regions
        if r["status"] in ("ready", "fixture-ready-renderer-not-wired")
    )
    unresolved_regions = sum(1 for r in regions if r["status"] == "unresolved")

    captured_at = source["captured_at"]
    # Derive snapshot date portion from capture metadata only (no wall clock).
    date_token = str(captured_at)[:10]

    fixture: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "fixture_kind": FIXTURE_KIND,
        "fixture_id": f"bukgu_gwangju.home.clone.{date_token}",
        "route_id": "home",
        "site_id": meta.get("site_id") or "bukgu_gwangju",
        "site_name": meta.get("site_name") or "",
        "page_id": "home",
        "status": "fixture_ready_renderer_not_wired",
        "clone_status": "capture_required",
        "management_mode": "generator_output_committed_raw_capture_source_of_truth",
        "source_identity": {
            "route_id": "home",
            "requested_url": source["requested_url"],
            "final_url": source["final_resolved_url"],
            "title": source["official_page_title"],
            "captured_at": captured_at,
            "raw_capture_sha256": source["raw_content_sha256"],
            "raw_byte_length": source["raw_byte_length"],
            "capture_metadata_sha256": meta["metadata_sha256"],
            "navigation_inventory_sha256": sha256_bytes(NAV_PATH.read_bytes()),
            "asset_inventory_sha256": sha256_bytes(ASSET_PATH.read_bytes()),
            "capture_notes_sha256": sha256_bytes(NOTES_PATH.read_bytes()),
            "generator_id": GENERATOR_ID,
            "generator_version": GENERATOR_VERSION,
            "capture_tool": source.get("capture_tool"),
            "capture_method": source.get("capture_method"),
        },
        "inputs": {
            "raw_snapshot": meta["files"]["raw_snapshot"],
            "capture_metadata": "data/official_captures/bukgu_gwangju/home/capture-metadata.json",
            "navigation_inventory": meta["files"]["navigation_inventory"],
            "asset_inventory": meta["files"]["asset_inventory"],
            "capture_notes": meta["files"]["capture_notes"],
        },
        "hierarchy": list(nav.get("hierarchy") or []),
        "regions": regions,
        "navigation": navigation_items,
        "assets": asset_items,
        "counts": {
            "regions": len(regions),
            "regions_ready": ready_regions,
            "regions_unresolved": unresolved_regions,
            "navigation_items": len(navigation_items),
            "navigation_blank_labels": nav.get("blank_label_count"),
            "assets": len(asset_items),
            "assets_ready_with_local_exact": ready_assets,
            "assets_unresolved": unresolved_assets,
            "capture_hierarchy_nodes": len(nav.get("hierarchy") or []),
        },
        "boundaries": {
            "network_at_generation": 0,
            "official_site_access": 0,
            "provider_api": 0,
            "firecrawl": 0,
            "ui_renderer_wired": False,
            "exact_clone_claimed": False,
            "home_remains_capture_required": True,
        },
    }

    fixture["fixture_sha256"] = fixture_body_checksum(fixture)
    return fixture


def write_fixture(fixture: dict[str, Any]) -> Path:
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = stable_dump(fixture)
    FIXTURE_PATH.write_text(text, encoding="utf-8", newline="\n")
    return FIXTURE_PATH


def check_fixture() -> list[str]:
    """Return human-readable problems if committed fixture is stale/wrong."""
    problems: list[str] = []
    expected = build_fixture()
    expected_text = stable_dump(expected)
    if not FIXTURE_PATH.is_file():
        problems.append(f"missing fixture: {FIXTURE_PATH}")
        return problems
    actual_text = FIXTURE_PATH.read_text(encoding="utf-8")
    if actual_text != expected_text:
        problems.append("committed fixture is not byte-identical to regenerated output")
    try:
        actual = json.loads(actual_text)
    except json.JSONDecodeError:
        problems.append("committed fixture is not valid JSON")
        return problems
    if actual.get("fixture_sha256") != expected.get("fixture_sha256"):
        problems.append("fixture_sha256 drift")
    if actual.get("source_identity", {}).get("raw_capture_sha256") != expected[
        "source_identity"
    ]["raw_capture_sha256"]:
        problems.append("raw capture identity drift")
    if actual.get("source_identity", {}).get("capture_metadata_sha256") != expected[
        "source_identity"
    ]["capture_metadata_sha256"]:
        problems.append("capture metadata identity drift")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed fixture matches regeneration from captures",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print fixture JSON to stdout instead of writing",
    )
    args = parser.parse_args(argv)

    try:
        if args.check:
            problems = check_fixture()
            if problems:
                for problem in problems:
                    print(f"[home-clone-fixture] FAIL: {problem}")
                return 1
            print("[home-clone-fixture] committed fixture is current")
            return 0

        fixture = build_fixture()
        text = stable_dump(fixture)
        if args.stdout:
            sys.stdout.write(text)
            return 0
        path = write_fixture(fixture)
        print(f"[home-clone-fixture] wrote {path.relative_to(ROOT)}")
        print(f"[home-clone-fixture] fixture_sha256={fixture['fixture_sha256']}")
        print(
            "[home-clone-fixture] counts="
            + json.dumps(fixture["counts"], ensure_ascii=False, sort_keys=True)
        )
        return 0
    except FixtureBuildError as exc:
        print(f"[home-clone-fixture] error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
