"""Offline contracts for #1166 canonical home clone fixture.

Consumes only committed #1160 capture inventory + generator helpers.
Zero network: any unexpected socket/urlopen use fails the suite.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOME_CAPTURE = ROOT / "data" / "official_captures" / "bukgu_gwangju" / "home"
META_PATH = HOME_CAPTURE / "capture-metadata.json"
NAV_PATH = HOME_CAPTURE / "navigation-inventory.json"
ASSET_PATH = HOME_CAPTURE / "asset-inventory.json"
RAW_PATH = HOME_CAPTURE / "raw-homepage.html"
FIXTURE_PATH = ROOT / "data" / "official_clone_fixtures" / "bukgu_gwangju" / "home.json"
GENERATOR_PATH = ROOT / "scripts" / "build_official_home_clone_fixture.py"
READINESS_PATH = ROOT / "docs" / "artifacts" / "1166-home-renderer-readiness.md"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
APPROVED_PREFIX = "https://bukgu.gwangju.kr"
FORBIDDEN_PLACEHOLDERS = ("-", "TBD", "TODO", "N/A", "placeholder")


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "build_official_home_clone_fixture", GENERATOR_PATH
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


gen = _load_generator()


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch):
    """Fail immediately if any routine test attempts network I/O."""

    def _blocked(*_a, **_k):
        raise AssertionError("network access is forbidden in #1166 tests")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    try:
        import urllib.request as ureq

        monkeypatch.setattr(ureq, "urlopen", _blocked)
    except Exception:
        pass
    try:
        import http.client as http_client

        monkeypatch.setattr(http_client.HTTPConnection, "connect", _blocked)
        monkeypatch.setattr(http_client.HTTPSConnection, "connect", _blocked)
    except Exception:
        pass


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ── Input integrity ────────────────────────────────────────────────


def test_input_capture_files_exist():
    for path in (META_PATH, NAV_PATH, ASSET_PATH, RAW_PATH, FIXTURE_PATH, GENERATOR_PATH):
        assert path.is_file(), f"missing {path}"


def test_raw_capture_checksum_matches_metadata():
    meta = _load_json(META_PATH)
    raw = RAW_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == meta["source"]["raw_content_sha256"]
    assert len(raw) == meta["source"]["raw_byte_length"]
    assert b"\r" not in raw


def test_metadata_checksum_matches_committed_file():
    meta = _load_json(META_PATH)
    assert SHA256_RE.fullmatch(meta["metadata_sha256"])
    assert gen.metadata_checksum(meta) == meta["metadata_sha256"]


def test_capture_route_and_source_url_identity():
    meta = _load_json(META_PATH)
    assert meta["route_id"] == "home"
    source = meta["source"]
    assert source["requested_url"].startswith(APPROVED_PREFIX)
    assert source["final_resolved_url"].startswith(APPROVED_PREFIX)
    assert source["requested_url"].startswith("https://")
    assert source["official_page_title"].strip()


# ── Determinism / generation ───────────────────────────────────────


def test_generation_is_byte_identical_and_checksum_stable():
    fixture_a = gen.build_fixture()
    fixture_b = gen.build_fixture()
    text_a = gen.stable_dump(fixture_a)
    text_b = gen.stable_dump(fixture_b)
    assert text_a == text_b
    assert fixture_a["fixture_sha256"] == fixture_b["fixture_sha256"]
    assert SHA256_RE.fullmatch(fixture_a["fixture_sha256"])
    # Self-checksum matches body excluding fixture_sha256
    assert gen.fixture_body_checksum(fixture_a) == fixture_a["fixture_sha256"]


def test_committed_fixture_matches_regeneration():
    problems = gen.check_fixture()
    assert problems == [], problems
    committed = FIXTURE_PATH.read_text(encoding="utf-8")
    expected = gen.stable_dump(gen.build_fixture())
    assert committed == expected


def test_generation_does_not_read_wall_clock(monkeypatch: pytest.MonkeyPatch):
    """Guard against time.time leakage during build; captured_at comes from metadata."""
    import time as time_mod

    def _fail_time(*_a, **_k):
        raise AssertionError("wall clock read forbidden during fixture generation")

    monkeypatch.setattr(time_mod, "time", _fail_time)
    monkeypatch.setattr(time_mod, "monotonic", _fail_time)
    fixture = gen.build_fixture()
    assert fixture["source_identity"]["captured_at"] == _load_json(META_PATH)["source"][
        "captured_at"
    ]
    # Fixture must not invent a generation timestamp field from wall clock.
    assert "generated_at" not in fixture
    assert "generated_at" not in fixture["source_identity"]


def test_generator_main_check_exit_zero():
    assert gen.main(["--check"]) == 0


# ── Hierarchy / order ──────────────────────────────────────────────


def test_hierarchy_and_navigation_order_preserved():
    fixture = _load_json(FIXTURE_PATH)
    nav_capture = _load_json(NAV_PATH)

    assert fixture["hierarchy"] == nav_capture["hierarchy"]
    assert fixture["counts"]["navigation_items"] == nav_capture["item_count"]
    assert len(fixture["navigation"]) == nav_capture["item_count"]

    orders = [item["order"] for item in fixture["navigation"]]
    assert orders == list(range(1, len(orders) + 1))
    assert orders == [item["order"] for item in nav_capture["items"]]

    # Footer items preserve relative order from capture.
    footer_orders = [
        item["order"]
        for item in fixture["navigation"]
        if item["region_identity"] == "footer"
    ]
    assert footer_orders == sorted(footer_orders)

    ids = [item["item_id"] for item in fixture["navigation"]]
    assert len(ids) == len(set(ids))

    for item in fixture["navigation"]:
        assert isinstance(item["depth"], int) and item["depth"] >= 0
        assert isinstance(item["ancestor_hierarchy"], list)
        assert item["dom_order"] == item["order"]


def test_region_ids_unique_and_top_level_order_stable():
    fixture = _load_json(FIXTURE_PATH)
    region_ids = [r["region_id"] for r in fixture["regions"]]
    assert len(region_ids) == len(set(region_ids))
    # Hierarchy nodes first in capture order
    hierarchy_regions = [r for r in fixture["regions"] if r["region_id"].startswith("hierarchy_")]
    assert [r["region_id"] for r in hierarchy_regions] == [
        f"hierarchy_{node['section']}" for node in fixture["hierarchy"]
    ]


# ── Source fidelity ────────────────────────────────────────────────


def test_all_labels_originate_from_capture_no_synthetic_or_placeholder():
    fixture = _load_json(FIXTURE_PATH)
    nav_capture = _load_json(NAV_PATH)
    capture_by_order = {item["order"]: item for item in nav_capture["items"]}

    for item in fixture["navigation"]:
        src = capture_by_order[item["order"]]
        assert item["label"] == (src.get("visible_label") or "")
        assert item["label_source"] == src.get("label_source")
        assert item["href"] == src.get("source_url")
        assert item["resolved_url"] == src.get("resolved_url")
        # Nonblank labels must not be synthetic placeholders.
        label = item["label"]
        if isinstance(label, str) and label.strip():
            assert label.strip() not in FORBIDDEN_PLACEHOLDERS
            assert "TBD" not in label
            assert label != "-"

    # Every capture navigation item is represented (no omission).
    assert {i["order"] for i in fixture["navigation"]} == set(capture_by_order)


def test_fixture_status_keeps_home_capture_required():
    fixture = _load_json(FIXTURE_PATH)
    assert fixture["schema_version"] == 1
    assert fixture["fixture_kind"] == "official_home_clone_fixture"
    assert fixture["route_id"] == "home"
    assert fixture["clone_status"] == "capture_required"
    assert fixture["boundaries"]["home_remains_capture_required"] is True
    assert fixture["boundaries"]["exact_clone_claimed"] is False
    assert fixture["boundaries"]["ui_renderer_wired"] is False
    assert fixture["boundaries"]["network_at_generation"] == 0


# ── Assets ─────────────────────────────────────────────────────────


def test_all_captured_assets_represented_and_partial_hash_not_full_identity():
    fixture = _load_json(FIXTURE_PATH)
    assets_capture = _load_json(ASSET_PATH)
    assert len(fixture["assets"]) == assets_capture["item_count"]
    assert fixture["counts"]["assets"] == assets_capture["item_count"]

    for asset in fixture["assets"]:
        assert asset["asset_id"]
        assert asset["local_availability"] in (
            "unresolved",
            "ready-with-existing-local-asset",
        )
        if asset["hash_scope"] == "first_65536_bytes":
            inv = asset.get("inventory_sha256")
            hashed = asset.get("hashed_byte_count")
            size = asset["captured_inventory_identity"].get("size_bytes")
            # If partial window did not cover whole file, must stay unresolved.
            if (
                isinstance(size, int)
                and isinstance(hashed, int)
                and hashed < size
                and inv
            ):
                assert asset["local_availability"] == "unresolved"
                assert "partial hash" in (asset.get("unresolved_reason") or "")

        if asset["local_availability"] == "ready-with-existing-local-asset":
            evidence = asset.get("identity_evidence") or []
            assert any("matching_full_file_sha256" in e for e in evidence)
            assert asset["local_candidate_path"]
            path = ROOT / asset["local_candidate_path"]
            assert path.is_file()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == asset["inventory_sha256"]
        else:
            assert asset["status"] == "unresolved-asset"
            assert asset.get("unresolved_reason")


def test_asset_ids_unique():
    fixture = _load_json(FIXTURE_PATH)
    ids = [a["asset_id"] for a in fixture["assets"]]
    assert len(ids) == len(set(ids))


# ── Drift ──────────────────────────────────────────────────────────


def test_raw_capture_change_without_regeneration_fails(tmp_path: Path, monkeypatch):
    original = RAW_PATH.read_bytes()
    try:
        RAW_PATH.write_bytes(original + b"<!--drift-->\n")
        with pytest.raises(gen.FixtureBuildError):
            gen.build_fixture()
    finally:
        RAW_PATH.write_bytes(original)


def test_metadata_checksum_change_fails(tmp_path: Path):
    meta = _load_json(META_PATH)
    meta["metadata_sha256"] = "0" * 64
    # Write corrupted meta temporarily
    original = META_PATH.read_text(encoding="utf-8")
    try:
        META_PATH.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        with pytest.raises(gen.FixtureBuildError):
            gen.build_fixture()
    finally:
        META_PATH.write_text(original, encoding="utf-8", newline="\n")


def test_manual_fixture_edit_fails_check(tmp_path: Path):
    original = FIXTURE_PATH.read_text(encoding="utf-8")
    try:
        dirty = original.replace(
            '"clone_status": "capture_required"',
            '"clone_status": "exact"',
            1,
        )
        assert dirty != original
        FIXTURE_PATH.write_text(dirty, encoding="utf-8", newline="\n")
        problems = gen.check_fixture()
        assert problems, "manual fixture edit must be detected"
    finally:
        FIXTURE_PATH.write_text(original, encoding="utf-8", newline="\n")


# ── Readiness report ───────────────────────────────────────────────


def test_renderer_readiness_report_exists_and_is_not_exact_claim():
    assert READINESS_PATH.is_file()
    text = READINESS_PATH.read_text(encoding="utf-8")
    assert "capture_required" in text
    assert "fixture" in text.lower()
    lowered = text.lower()
    assert "home exact clone 완료" not in lowered
    assert "home is an exact official clone" not in lowered
    assert "exact clone claimed" not in lowered
    for token in (
        "ready",
        "unresolved",
        "fixture-ready-renderer-not-wired",
    ):
        assert token in lowered or token.replace("-", " ") in lowered
