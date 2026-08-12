"""Offline contracts for #1303 G2-A reference clone model.

Builds the renderer-agnostic semantic clone model from the committed G1 named-site
reference capture ledger + committed artifacts. Zero network: any unexpected
socket/urlopen use fails the suite.

Fail-closed contract checks:
  * input capture root is selected explicitly (no glob discovery)
  * plan identity checksum, artifact containment/presence/SHA-256, state
    completeness, and inventory validity all gate the build
  * reference_baseline_ready is derived, never a constant
  * the model is a semantic layer (page title, landmarks, controls, asset
    provenance, exceptions, download signals) so a later renderer need not
    read raw G1 artifacts
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import socket
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "official_clone" / "reference_clone_model.py"
GENERATOR_PATH = REPO_ROOT / "scripts" / "build_reference_clone_model.py"
CAPTURE_ROOT = (
    REPO_ROOT
    / "data"
    / "official_captures"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
)
FIXTURE_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_fixtures"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
    / "clone-model.json"
)
LEDGER_PATH = CAPTURE_ROOT / "ledger.json"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Stronger claims must stay False in G2-A.
FORBIDDEN_STRONGER_CLAIM = (
    "faithful_clone_candidate",
    "clone_mvp_ready",
    "visual_approval",
    "actual_site_integrated",
)

VALIDATION_KEYS = (
    "ledger_identity_valid",
    "states_complete",
    "artifacts_within_capture_root",
    "artifact_files_present",
    "artifact_sha256_match",
    "inventories_valid",
    "reference_baseline_ready",
)


def _load_module():
    spec = importlib.util.spec_from_file_location("reference_clone_model", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch):
    """Fail immediately if any routine test attempts network I/O."""

    def _blocked(*_a, **_k):
        raise AssertionError("network access is forbidden in G2-A tests")

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


def test_input_files_exist():
    for path in (LEDGER_PATH, FIXTURE_PATH, MODULE_PATH, GENERATOR_PATH):
        assert path.is_file(), f"missing {path}"


def test_builder_requires_explicit_capture_root():
    with pytest.raises(mod.ReferenceCloneModelError):
        mod.build_reference_clone_model(REPO_ROOT, None)


def test_generator_module_is_not_site_specific():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "seogu_gwangju" not in source, "generator must not hardcode the seogu site id"
    assert "offline_preview" not in source, "must not rename/extend offline_preview to bypass"
    assert "glob(" not in source, "input ledger must be selected explicitly, not by glob"
    assert 'site_id == "' not in source
    assert "== 'seogu" not in source


# ── Determinism / generation ───────────────────────────────────────


def test_generation_is_byte_identical_and_checksum_stable():
    model_a = mod.build_reference_clone_model(REPO_ROOT, CAPTURE_ROOT)
    model_b = mod.build_reference_clone_model(REPO_ROOT, CAPTURE_ROOT)
    assert mod.stable_dump(model_a) == mod.stable_dump(model_b)
    assert model_a["model_sha256"] == model_b["model_sha256"]
    assert SHA256_RE.fullmatch(model_a["model_sha256"])


def test_committed_fixture_matches_regeneration():
    problems = mod.check_model(REPO_ROOT, CAPTURE_ROOT)
    assert problems == [], problems
    committed = FIXTURE_PATH.read_text(encoding="utf-8")
    expected = mod.stable_dump(mod.build_reference_clone_model(REPO_ROOT, CAPTURE_ROOT))
    assert committed == expected


def test_generator_main_check_exit_zero():
    assert mod.main(["--check", "--capture-root", str(CAPTURE_ROOT)]) == 0


def test_no_wall_clock_during_build(monkeypatch: pytest.MonkeyPatch):
    import time as time_mod

    def _fail_time(*_a, **_k):
        raise AssertionError("wall clock read forbidden during model build")

    monkeypatch.setattr(time_mod, "time", _fail_time)
    monkeypatch.setattr(time_mod, "monotonic", _fail_time)
    model = mod.build_reference_clone_model(REPO_ROOT, CAPTURE_ROOT)
    assert "generated_at" not in model
    assert "generated_at" not in model.get("source_identity", {})


# ── Schema / derived claims ────────────────────────────────────────


def test_schema_and_kind():
    model = _load_json(FIXTURE_PATH)
    assert model["schema_version"] == 1
    assert model["model_kind"] == "reference_clone_model"
    assert model["site_id"] == "seogu_gwangju"
    assert model["capture_id"] == "20260812T231018-0900"
    assert model["capture_mode"] == "controlled_read_only_reference"


def test_reference_baseline_ready_is_derived_not_constant():
    """reference_baseline_ready must come from the validation report."""
    model = _load_json(FIXTURE_PATH)
    validation = model["validation"]
    for key in VALIDATION_KEYS:
        assert key in validation, f"missing derived validation field {key}"
        assert isinstance(validation[key], bool)
    # Derived AND gate: equals the AND of every constituent gate.
    assert validation["reference_baseline_ready"] == all(
        validation[key] for key in VALIDATION_KEYS if key != "reference_baseline_ready"
    )
    assert model["claim_gates"]["reference_baseline_ready"] == validation["reference_baseline_ready"]
    assert model["claim_gates"]["reference_baseline_ready"] is True


def test_claim_gates_are_fail_closed_at_g2a():
    gates = _load_json(FIXTURE_PATH)["claim_gates"]
    for claim in FORBIDDEN_STRONGER_CLAIM:
        assert gates[claim] is False, f"{claim} must stay False in G2-A"
    assert gates["reference_baseline_ready"] is True
    assert gates["reference_semantic_model_ready"] is True


def test_boundaries_block_runtime_screenshot_and_renderer():
    boundaries = _load_json(FIXTURE_PATH)["boundaries"]
    assert boundaries["screenshot_used_at_runtime"] is False
    assert boundaries["network_at_generation"] == 0
    assert boundaries["renderer_wired"] is False
    assert boundaries["exact_clone_claimed"] is False


def test_provenance_manifest_and_exception_queue_present():
    model = _load_json(FIXTURE_PATH)
    assert "provenance_manifest" in model
    assert isinstance(model["provenance_manifest"], list)
    assert model["provenance_manifest"]
    assert "exception_queue" in model
    assert isinstance(model["exception_queue"], list)
    assert model["exception_queue"]


def test_provenance_manifest_entries_have_required_fields():
    model = _load_json(FIXTURE_PATH)
    for entry in model["provenance_manifest"]:
        assert "state_id" in entry
        assert "source_url" in entry
        assert "sha256" in entry
        assert "provenance_note" in entry


def test_exception_queue_entries_have_required_fields():
    model = _load_json(FIXTURE_PATH)
    for entry in model["exception_queue"]:
        assert "state_id" in entry
        assert "code" in entry
        assert "detail" in entry


# ── G1 evidence derivation ─────────────────────────────────────────


def test_state_and_artifact_counts_match_g1():
    model = _load_json(FIXTURE_PATH)
    assert model["state_count"] == 11
    assert model["artifact_count"] == 44
    assert len(model["states"]) == 11
    assert sum(len(s["artifacts"]) for s in model["states"]) == 44


def test_ledger_artifact_sha256_links_to_committed_bytes():
    """The model must connect each ledger artifact to its real committed bytes."""
    model = _load_json(FIXTURE_PATH)
    checked = 0
    for state in model["states"]:
        for artifact in state["artifacts"]:
            path = REPO_ROOT / artifact["artifact_id"]
            assert path.is_file(), f"artifact file missing: {artifact['artifact_id']}"
            assert SHA256_RE.fullmatch(artifact["sha256"] or "")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual == artifact["sha256"], (
                f"artifact sha256 mismatch for {artifact['artifact_id']}"
            )
            checked += 1
    assert checked == 44


def test_model_is_semantic_layer_with_observed_content():
    """Renderer must not need to read raw G1 artifacts."""
    model = _load_json(FIXTURE_PATH)
    by_id = {s["state_id"]: s for s in model["states"]}
    for state in model["states"]:
        assert isinstance(state["page_title"], str) and state["page_title"]
        assert isinstance(state["landmarks"], list)
        assert isinstance(state["controls"], list)
        assert isinstance(state["public_assets"], list)
        assert isinstance(state["exceptions"], list)
        assert isinstance(state["captured_at"], str) and state["captured_at"]
        assert state["final_http_status"] is None or isinstance(state["final_http_status"], int)
    # Observed header/nav/main content and controls are present.
    home = by_id["home.desktop.default"]
    assert home["landmarks"], "home landmarks must be captured"
    assert home["controls"], "home controls must be captured"
    assert any(l["tag"] == "header" for l in home["landmarks"]), "header landmark expected"


def test_home_page_title_reflects_actual_content():
    model = _load_json(FIXTURE_PATH)
    by_id = {s["state_id"]: s for s in model["states"]}
    home = by_id["home.desktop.default"]
    assert "서구청" in home["page_title"]
    assert "착한도시 서구" in home["page_title"]


def test_home_landmark_has_header_nav_main():
    model = _load_json(FIXTURE_PATH)
    by_id = {s["state_id"]: s for s in model["states"]}
    home = by_id["home.desktop.default"]
    tags = [l["tag"] for l in home["landmarks"]]
    assert "header" in tags
    assert "nav" in tags
    assert "main" in tags


def test_notice_list_and_detail_remain_distinct():
    model = _load_json(FIXTURE_PATH)
    by_id = {s["state_id"]: s for s in model["states"]}
    notice_list = by_id["notice.list.desktop"]
    notice_detail = by_id["notice.detail.desktop"]
    assert notice_list["state_id"] != notice_detail["state_id"]
    assert notice_list["requested_url"] != notice_detail["requested_url"]
    assert notice_list["page_title"] != notice_detail["page_title"]
    assert notice_list["landmarks"] != notice_detail["landmarks"]
    assert notice_detail["list_no"] == "143106"
    # Detail has download references; list typically does not (no single detail).
    assert notice_detail["download_references"]


def test_gosi_list_and_detail_remain_distinct():
    model = _load_json(FIXTURE_PATH)
    by_id = {s["state_id"]: s for s in model["states"]}
    gosi_list = by_id["gosi.list.desktop"]
    gosi_detail = by_id["gosi.detail.desktop"]
    assert gosi_list["state_id"] != gosi_detail["state_id"]
    assert gosi_list["requested_url"] != gosi_detail["requested_url"]
    assert gosi_list["page_title"] != gosi_detail["page_title"]
    assert gosi_list["landmarks"] != gosi_detail["landmarks"]


def test_organization_and_staff_remain_distinct():
    model = _load_json(FIXTURE_PATH)
    by_id = {s["state_id"]: s for s in model["states"]}
    org = by_id["organization.chart.desktop"]
    staff = by_id["staff.directory.desktop"]
    assert org["state_id"] != staff["state_id"]
    assert org["requested_url"] != staff["requested_url"]
    assert org["page_title"] != staff["page_title"]
    assert org["landmarks"] != staff["landmarks"]


def test_notice_detail_derives_list_no_143106_with_attachment():
    model = _load_json(FIXTURE_PATH)
    notice = next(s for s in model["states"] if s["state_id"] == "notice.detail.desktop")
    assert notice["list_no"] == "143106"
    assert notice["state_name"] == "detail_with_attachment_state"
    assert notice["download_references"]
    assert any(r["href"] for r in notice["download_references"])


def test_civil_form_detail_derives_list_no_143010_hwp():
    model = _load_json(FIXTURE_PATH)
    civil = next(s for s in model["states"] if s["state_id"] == "civil_form.detail.desktop")
    assert civil["list_no"] == "143010"
    assert civil["state_name"] == "detail_with_download_state"
    assert civil["download_references"]
    assert "hwp" in civil["attachment_document_extensions"]


def test_gnb_open_and_device_class_derived():
    model = _load_json(FIXTURE_PATH)
    by_id = {s["state_id"]: s for s in model["states"]}
    assert by_id["home.desktop.gnb_open"]["state_name"] == "gnb_open"
    assert by_id["home.desktop.gnb_open"]["device_class"] == "desktop"
    assert by_id["home.mobile.default"]["device_class"] == "mobile"
    assert by_id["home.desktop.default"]["device_class"] == "desktop"


def test_asset_provenance_and_exceptions_captured():
    model = _load_json(FIXTURE_PATH)
    notice = next(s for s in model["states"] if s["state_id"] == "notice.detail.desktop")
    assert notice["public_assets"]
    for asset in notice["public_assets"]:
        assert asset["source_url"].startswith("https://www.seogu.gwangju.kr/")
        assert SHA256_RE.fullmatch(asset["sha256"])
    # Capture-time blocked-request exceptions are preserved as observations.
    assert notice["exceptions"]


def test_source_identity_references_g1_ledger_and_plan():
    model = _load_json(FIXTURE_PATH)
    identity = model["source_identity"]
    assert identity["ledger_path"].endswith("ledger.json")
    assert SHA256_RE.fullmatch(identity["ledger_sha256"])
    assert identity["plan_id"] == "seogu_gwangju.g1.v1"
    assert identity["plan_path"] == "configs/reference-plans/seogu_gwangju.json"
    assert SHA256_RE.fullmatch(identity["plan_sha256"])
    assert identity["allowed_hosts"] == ["www.seogu.gwangju.kr"]
    assert identity["g1_completion_claim"] is True


def test_per_state_timestamps_and_status_preserved():
    model = _load_json(FIXTURE_PATH)
    for state in model["states"]:
        assert "captured_at" in state
        assert "source_updated_at" in state
        assert "final_http_status" in state
    home = next(s for s in model["states"] if s["state_id"] == "home.desktop.default")
    assert home["captured_at"] == "2026-08-12T14:10:25.189Z"
    assert home["final_http_status"] == 200


def test_expected_identity_flags_work(tmp_path):
    """When expected site/capture identity matches, build succeeds."""
    repo_root, capture_root = _synthetic_capture(tmp_path)
    model = mod.build_reference_clone_model(repo_root, capture_root, "second_site", "20260813T010203-0900")
    assert model["site_id"] == "second_site"
    assert model["capture_id"] == "20260813T010203-0900"


def test_main_cli_accepts_expected_identity():
    """CLI --expected-site-id/--capture-id flags work with real capture."""
    assert mod.main(["--check", "--capture-root", str(CAPTURE_ROOT),
                    "--expected-site-id", "seogu_gwangju",
                    "--expected-capture-id", "20260812T231018-0900"]) == 0


# ── Input non-mutation ─────────────────────────────────────────────


def test_builder_does_not_mutate_ledger_bytes():
    original = LEDGER_PATH.read_bytes()
    original_sha = hashlib.sha256(original).hexdigest()
    mod.build_reference_clone_model(REPO_ROOT, CAPTURE_ROOT)
    assert LEDGER_PATH.read_bytes() == original
    assert hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest() == original_sha


def test_builder_does_not_mutate_artifact_bytes():
    """Check one representative artifact is not mutated by the builder."""
    html_path = CAPTURE_ROOT / "states" / "home.desktop.default" / "source.html"
    original = html_path.read_bytes()
    original_sha = hashlib.sha256(original).hexdigest()
    mod.build_reference_clone_model(REPO_ROOT, CAPTURE_ROOT)
    assert html_path.read_bytes() == original
    assert hashlib.sha256(html_path.read_bytes()).hexdigest() == original_sha


# ── Fail-closed negative tests (synthetic captures) ────────────────

SITE_ID = "second_site"
CAP_ID = "20260813T010203-0900"

EXPECTED_STATES = ["home.desktop.default"]


def _synthetic_capture(tmp_path: Path, tamper: Callable[[Path, Path, Path], None] | None = None):
    repo_root = tmp_path
    site_id, capture_id = SITE_ID, CAP_ID
    capture_root = repo_root / "data" / "official_captures" / site_id / "g1" / capture_id
    states_dir = capture_root / "states" / "home.desktop.default"
    states_dir.mkdir(parents=True)

    html_path = states_dir / "source.html"
    html = '<html><head><title>Second</title></head><body><a href="/boardDownload.es?list_no=7">dl</a></body></html>\n'
    html_path.write_text(html, encoding="utf-8", newline="\n")

    inventory = {
        "title": "Second",
        "viewport": {"width": 1440, "height": 900},
        "landmarks": [{"tag": "header", "text": "Nav", "id": "header", "class_name": ""}],
        "controls": [{"tag": "a", "text": "link", "id": None, "class_name": ""}],
    }
    inventory_path = states_dir / "visible-region-inventory.json"
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )

    plan = {
        "schema_version": "1.0.0",
        "kind": "named_site_reference_capture_plan",
        "plan_id": f"{site_id}.g1.v1",
        "site_id": site_id,
        "capture_mode": "controlled_read_only_reference",
        "allowed_hosts": [f"www.{site_id}.example"],
        "allowed_methods": ["GET"],
        "routine_ci": {"network_policy": "offline"},
        "security_boundary": {},
        "completion_policy": {
            "g1_completion_claim": False,
            "executed_ledger_required": True,
            "uncaptured_state_policy": "capture_required_exception",
        },
        "states": [
            {
                "state_id": "home.desktop.default",
                "source_seed_url": f"https://www.{site_id}.example/",
                "viewport": {"width": 1440, "height": 900},
                "state": {"name": "default"},
                "required_artifacts": ["html_dom_content", "visible_region_inventory"],
                "freeze_at_capture": False,
                "capture_required": True,
            }
        ],
    }
    plan_rel = f"configs/reference-plans/{site_id}.json"
    plan_path = repo_root / plan_rel
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_bytes = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    plan_path.write_bytes(plan_bytes)
    plan_sha = hashlib.sha256(plan_bytes).hexdigest()

    html_sha = hashlib.sha256(html_path.read_bytes()).hexdigest()
    inventory_sha = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    prefix = f"data/official_captures/{site_id}/g1/{capture_id}/"

    ledger = {
        "schema_version": "1.0.0",
        "kind": "named_site_reference_capture_ledger",
        "site_id": site_id,
        "capture_mode": "controlled_read_only_reference",
        "plan_identity": {"plan_id": f"{site_id}.g1.v1", "path": plan_rel, "sha256": plan_sha},
        "g1_completion_claim": True,
        "captured_states": [
            {
                "state_id": "home.desktop.default",
                "requested_url": f"https://www.{site_id}.example/",
                "final_url": f"https://www.{site_id}.example/",
                "captured_at": "2026-08-13T01:02:03+09:00",
                "source_updated_at": None,
                "final_http_status": 200,
                "viewport": {"width": 1440, "height": 900},
                "state": {"name": "default"},
                "artifacts": [
                    {
                        "class": "html_dom_content",
                        "artifact_id": f"{prefix}states/home.desktop.default/source.html",
                        "sha256": html_sha,
                        "mime_type": "text/html; charset=utf-8",
                    },
                    {
                        "class": "visible_region_inventory",
                        "artifact_id": f"{prefix}states/home.desktop.default/visible-region-inventory.json",
                        "sha256": inventory_sha,
                        "mime_type": "application/json",
                    },
                ],
                "public_assets": [],
                "exceptions": [],
                "result_status": "success",
            }
        ],
    }
    ledger_path = capture_root / "ledger.json"
    ledger_path.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    if tamper is not None:
        tamper(repo_root, capture_root, ledger_path)
    return repo_root, capture_root


def test_synthetic_second_site_builds_valid_generic_model(tmp_path):
    """The builder is generic: a second-site capture builds a valid model."""
    repo_root, capture_root = _synthetic_capture(tmp_path)
    validation = mod.validate_reference_evidence(repo_root, capture_root)
    assert validation["reference_baseline_ready"] is True
    model = mod.build_reference_clone_model(repo_root, capture_root)
    assert model["site_id"] == "second_site"
    assert model["state_count"] == 1
    assert model["artifact_count"] == 2
    assert model["claim_gates"]["reference_baseline_ready"] is True
    assert model["claim_gates"]["reference_semantic_model_ready"] is True
    assert model["claim_gates"]["faithful_clone_candidate"] is False
    # Top-level aggregates available on synthetic model too.
    assert "provenance_manifest" in model
    assert "exception_queue" in model
    state = model["states"][0]
    assert state["page_title"] == "Second"
    assert state["landmarks"][0]["tag"] == "header"
    assert state["captured_at"] == "2026-08-13T01:02:03+09:00"
    assert state["final_http_status"] == 200


def _tamper_sha_mismatch(_repo, capture_root, _ledger_path):
    html = capture_root / "states" / "home.desktop.default" / "source.html"
    html.write_bytes(b"tampered content")


def _tamper_missing_artifact(_repo, capture_root, _ledger_path):
    html = capture_root / "states" / "home.desktop.default" / "source.html"
    html.unlink()


def _tamper_path_traversal(_repo, _capture_root, ledger_path):
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["captured_states"][0]["artifacts"][0]["artifact_id"] = "../../../../etc/passwd"
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _tamper_wrong_plan_identity(_repo, _capture_root, ledger_path):
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["plan_identity"]["sha256"] = "0" * 64
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _tamper_incomplete_g1(_repo, _capture_root, ledger_path):
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["captured_states"][0]["result_status"] = "failed"
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _tamper_invalid_inventory(_repo, capture_root, _ledger_path):
    inventory = capture_root / "states" / "home.desktop.default" / "visible-region-inventory.json"
    inventory.write_text("{}\n", encoding="utf-8", newline="\n")


def _tamper_g1_completion_false(_repo, _capture_root, ledger_path):
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["g1_completion_claim"] = False
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _tamper_duplicate_state(_repo, _capture_root, ledger_path):
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    dup = dict(ledger["captured_states"][0])
    ledger["captured_states"].append(dup)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _tamper_unknown_state(_repo, _capture_root, ledger_path):
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["captured_states"].append({
        "state_id": "unknown.extra.desktop",
        "requested_url": "https://example.com/",
        "final_url": "https://example.com/",
        "captured_at": "2026-08-13T01:02:03+09:00",
        "source_updated_at": None,
        "final_http_status": 200,
        "viewport": {"width": 1440, "height": 900},
        "state": {"name": "default"},
        "artifacts": [],
        "public_assets": [],
        "exceptions": [],
        "result_status": "success",
    })
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _tamper_wrong_site_id(_repo, _capture_root, ledger_path):
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["site_id"] = "wrong_site"
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _tamper_wrong_capture_id(tmp_path, _capture_root, _ledger_path):
    """Rename the capture root to produce an unexpected capture_id."""
    repo_root = tmp_path
    old = repo_root / "data" / "official_captures" / SITE_ID / "g1" / CAP_ID
    new = repo_root / "data" / "official_captures" / SITE_ID / "g1" / "wrong_capture"
    old.rename(new)


@pytest.mark.parametrize(
    "tamper,flag",
    [
        (_tamper_sha_mismatch, "artifact_sha256_match"),
        (_tamper_missing_artifact, "artifact_files_present"),
        (_tamper_path_traversal, "artifacts_within_capture_root"),
        (_tamper_wrong_plan_identity, "ledger_identity_valid"),
        (_tamper_incomplete_g1, "states_complete"),
        (_tamper_invalid_inventory, "inventories_valid"),
        (_tamper_g1_completion_false, "ledger_identity_valid"),
    ],
    ids=[
        "sha_mismatch",
        "missing_artifact",
        "path_traversal",
        "wrong_plan_identity",
        "incomplete_g1",
        "invalid_inventory",
        "g1_completion_false",
    ],
)
def test_tampered_g1_fails_closed(tmp_path, tamper, flag):
    repo_root, capture_root = _synthetic_capture(tmp_path, tamper=tamper)
    validation = mod.validate_reference_evidence(repo_root, capture_root)
    assert validation[flag] is False, f"{flag} must be False when tampered"
    assert validation["reference_baseline_ready"] is False
    with pytest.raises(mod.ReferenceCloneModelError):
        mod.build_reference_clone_model(repo_root, capture_root)


def test_duplicate_required_state_fails(tmp_path):
    repo_root, capture_root = _synthetic_capture(tmp_path, tamper=_tamper_duplicate_state)
    validation = mod.validate_reference_evidence(repo_root, capture_root)
    assert validation["states_complete"] is False
    assert validation["reference_baseline_ready"] is False
    with pytest.raises(mod.ReferenceCloneModelError):
        mod.build_reference_clone_model(repo_root, capture_root)


def test_unknown_additional_state_fails(tmp_path):
    repo_root, capture_root = _synthetic_capture(tmp_path, tamper=_tamper_unknown_state)
    validation = mod.validate_reference_evidence(repo_root, capture_root)
    assert validation["states_complete"] is False
    assert validation["reference_baseline_ready"] is False
    with pytest.raises(mod.ReferenceCloneModelError):
        mod.build_reference_clone_model(repo_root, capture_root)


def test_wrong_expected_site_id_fails(tmp_path):
    repo_root, capture_root = _synthetic_capture(tmp_path)
    validation = mod.validate_reference_evidence(repo_root, capture_root, expected_site_id="expected_other")
    assert validation["identity_mismatch"] is not None
    assert validation["ledger_identity_valid"] is False
    assert validation["reference_baseline_ready"] is False
    with pytest.raises(mod.ReferenceCloneModelError):
        mod.build_reference_clone_model(repo_root, capture_root, expected_site_id="expected_other")


def test_wrong_expected_capture_id_fails(tmp_path):
    repo_root, capture_root = _synthetic_capture(tmp_path)
    validation = mod.validate_reference_evidence(repo_root, capture_root, expected_capture_id="wrong_capture")
    assert validation["identity_mismatch"] is not None
    assert validation["ledger_identity_valid"] is False
    assert validation["reference_baseline_ready"] is False
    with pytest.raises(mod.ReferenceCloneModelError):
        mod.build_reference_clone_model(repo_root, capture_root, expected_capture_id="wrong_capture")