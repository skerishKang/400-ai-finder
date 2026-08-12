"""Offline contracts for #1303 G2-A reference clone model.

Builds the renderer-agnostic semantic clone model from the committed G1 named-site
reference capture ledger + committed artifacts. Zero network: any unexpected
socket/urlopen use fails the suite. Every field must be derived from G1 evidence;
stronger readiness claims are fail-closed at this stage.
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

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "official_clone" / "reference_clone_model.py"
GENERATOR_PATH = REPO_ROOT / "scripts" / "build_reference_clone_model.py"
FIXTURE_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_fixtures"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
    / "clone-model.json"
)
LEDGER_PATH = (
    REPO_ROOT
    / "data"
    / "official_captures"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
    / "ledger.json"
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Forbidden stronger-claim leakage in G2-A (fail-closed readiness gates).
FORBIDDEN_STRONGER_CLAIM = (
    "faithful_clone_candidate",
    "clone_mvp_ready",
    "visual_approval",
    "actual_site_integrated",
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


# ── Determinism / generation ───────────────────────────────────────


def test_generation_is_byte_identical_and_checksum_stable():
    model_a = mod.build_reference_clone_model(REPO_ROOT)
    model_b = mod.build_reference_clone_model(REPO_ROOT)
    text_a = mod.stable_dump(model_a)
    text_b = mod.stable_dump(model_b)
    assert text_a == text_b
    assert model_a["model_sha256"] == model_b["model_sha256"]
    assert SHA256_RE.fullmatch(model_a["model_sha256"])


def test_committed_fixture_matches_regeneration():
    problems = mod.check_model(REPO_ROOT)
    assert problems == [], problems
    committed = FIXTURE_PATH.read_text(encoding="utf-8")
    expected = mod.stable_dump(mod.build_reference_clone_model(REPO_ROOT))
    assert committed == expected


def test_generator_main_check_exit_zero():
    assert mod.main(["--check"]) == 0


# ── Schema / claim gates ───────────────────────────────────────────


def test_schema_and_kind():
    model = _load_json(FIXTURE_PATH)
    assert model["schema_version"] == 1
    assert model["model_kind"] == "reference_clone_model"
    assert model["site_id"] == "seogu_gwangju"
    assert model["capture_id"] == "20260812T231018-0900"
    assert model["capture_mode"] == "controlled_read_only_reference"


def test_claim_gates_are_fail_closed_at_g2a():
    gates = _load_json(FIXTURE_PATH)["claim_gates"]
    assert gates == {
        "reference_baseline_ready": True,
        "faithful_clone_candidate": False,
        "clone_mvp_ready": False,
        "visual_approval": False,
        "actual_site_integrated": False,
    }
    # No stronger claim may be true at this stage.
    for claim in FORBIDDEN_STRONGER_CLAIM:
        assert gates[claim] is False, f"{claim} must stay False in G2-A"


def test_boundaries_block_runtime_screenshot_and_renderer():
    boundaries = _load_json(FIXTURE_PATH)["boundaries"]
    assert boundaries["screenshot_used_at_runtime"] is False
    assert boundaries["network_at_generation"] == 0
    assert boundaries["renderer_wired"] is False
    assert boundaries["exact_clone_claimed"] is False


# ── G1 evidence derivation ─────────────────────────────────────────


def test_state_and_artifact_counts_match_g1():
    model = _load_json(FIXTURE_PATH)
    assert model["state_count"] == 11
    assert model["artifact_count"] == 44
    assert len(model["states"]) == 11
    total_artifacts = sum(len(s["artifacts"]) for s in model["states"])
    assert total_artifacts == 44


def test_device_class_derived_from_state_identity():
    model = _load_json(FIXTURE_PATH)
    by_id = {s["state_id"]: s for s in model["states"]}
    assert by_id["home.mobile.default"]["device_class"] == "mobile"
    assert by_id["home.desktop.default"]["device_class"] == "desktop"
    assert by_id["notice.detail.desktop"]["device_class"] == "desktop"
    assert by_id["home.desktop.gnb_open"]["device_class"] == "desktop"


def test_notice_detail_derives_list_no_143106_with_attachment():
    model = _load_json(FIXTURE_PATH)
    notice = next(s for s in model["states"] if s["state_id"] == "notice.detail.desktop")
    assert notice["list_no"] == "143106"
    assert notice["state_name"] == "detail_with_attachment_state"
    assert notice["download_references"], "notice detail must expose a download reference"
    assert any(r["href"] for r in notice["download_references"])


def test_civil_form_detail_derives_list_no_143010_hwp():
    model = _load_json(FIXTURE_PATH)
    civil = next(s for s in model["states"] if s["state_id"] == "civil_form.detail.desktop")
    assert civil["list_no"] == "143010"
    assert civil["state_name"] == "detail_with_download_state"
    assert civil["download_references"], "civil-form detail must expose a download reference"
    assert "hwp" in civil["attachment_document_extensions"], "HWP attachment must be evident from G1 html"


def test_gnb_open_state_present():
    model = _load_json(FIXTURE_PATH)
    gnb = next(s for s in model["states"] if s["state_id"] == "home.desktop.gnb_open")
    assert gnb["state_name"] == "gnb_open"
    assert gnb["result_status"] == "success"


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
                f"artifact sha256 mismatch for {artifact['artifact_id']}: "
                f"model={artifact['sha256']} file={actual}"
            )
            checked += 1
    assert checked == 44


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


# ── Generator must be generic (no site-specific branch) ────────────


def test_generator_module_is_not_site_specific():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "seogu_gwangju" not in source, "generator must not hardcode the seogu site id"
    assert "offline_preview" not in source, "must not rename/extend offline_preview to bypass"
    # No site-conditional branching on a literal site id.
    assert 'site_id == "' not in source
    assert "== 'seogu" not in source


def test_no_wall_clock_during_build(monkeypatch: pytest.MonkeyPatch):
    import time as time_mod

    def _fail_time(*_a, **_k):
        raise AssertionError("wall clock read forbidden during model build")

    monkeypatch.setattr(time_mod, "time", _fail_time)
    monkeypatch.setattr(time_mod, "monotonic", _fail_time)
    model = mod.build_reference_clone_model(REPO_ROOT)
    assert "generated_at" not in model
    assert "generated_at" not in model.get("source_identity", {})
