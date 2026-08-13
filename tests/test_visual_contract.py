"""Offline contracts for the #1303 G2-B visual contract validator.

Proves the visual contract is an executable gate, not a doc:

  * null contract -> ``faithful_ready`` False;
  * wrong site / capture id -> fail-closed;
  * wrong model checksum -> fail-closed;
  * malformed measurements (bad color, bad range, unknown provenance state,
    artifact SHA mismatch) -> fail-closed;
  * required schema fields present;
  * provenance state existence + artifact SHA matching;
  * numeric ranges enforced;
  * null/pending accounting is exact;
  * the committed visual contract validates against the committed model and is
    faithful-ready;
  * the committed asset manifest accounting is exact (total=879, committed=0,
    selected=0, unresolved=879, review_required=879) and deterministic;
  * measurement regeneration is deterministic (``--check`` passes).

No network, no live site, no screenshot runtime in the validator itself.
"""

from __future__ import annotations

import importlib
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_fixtures"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
    / "clone-model.json"
)
VISUAL_CONTRACT_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_visual_inputs"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
    / "visual-contract.json"
)
ASSET_MANIFEST_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_visual_inputs"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
    / "asset-manifest.json"
)
MEASURE_SCRIPT = REPO_ROOT / "scripts" / "measure_g1_visual_contract.py"


def _load_validator():
    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))
    return importlib.import_module("official_clone.visual_contract")


validator = _load_validator()


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch):
    def _blocked(*_a, **_k):
        raise AssertionError("network access is forbidden in visual contract tests")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    try:
        import urllib.request as ureq

        monkeypatch.setattr(ureq, "urlopen", _blocked)
    except Exception:
        pass


def _model():
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))


def _contract():
    return json.loads(VISUAL_CONTRACT_PATH.read_text(encoding="utf-8"))


def test_null_contract_fails_closed():
    with pytest.raises(validator.VisualContractValidationError):
        validator.validate_visual_contract(None, _model())
    assert validator.faithful_ready(None) is False
    assert validator.faithful_ready({}) is False


def test_wrong_site_id_fails_closed():
    contract = _contract()
    contract["site_id"] = "other_gwangju"
    with pytest.raises(validator.VisualContractValidationError, match="site_id mismatch"):
        validator.validate_visual_contract(contract, _model())


def test_wrong_capture_id_fails_closed():
    contract = _contract()
    contract["capture_id"] = "19990101T000000-0900"
    with pytest.raises(validator.VisualContractValidationError, match="capture_id mismatch"):
        validator.validate_visual_contract(contract, _model())


def test_wrong_model_checksum_fails_closed():
    contract = _contract()
    contract["model_checksum"] = "0" * 64
    with pytest.raises(validator.VisualContractValidationError, match="model_checksum mismatch"):
        validator.validate_visual_contract(contract, _model())


def test_wrong_contract_kind_fails_closed():
    contract = _contract()
    contract["contract_kind"] = "theme"
    with pytest.raises(validator.VisualContractValidationError, match="contract_kind"):
        validator.validate_visual_contract(contract, _model())


def test_wrong_schema_version_fails_closed():
    contract = _contract()
    contract["schema_version"] = 1
    with pytest.raises(validator.VisualContractValidationError, match="schema_version"):
        validator.validate_visual_contract(contract, _model())


def test_missing_required_section_fails_closed():
    contract = _contract()
    del contract["colors"]
    with pytest.raises(validator.VisualContractValidationError, match="missing required section"):
        validator.validate_visual_contract(contract, _model())


def test_malformed_color_fails_closed():
    contract = _contract()
    contract["colors"]["text"] = "#gggggg"
    # Sync the evidence so the failure is the malformed color itself.
    for entry in contract["measurements"]:
        if entry["field"] == "colors.text":
            entry["value"] = "#gggggg"
    with pytest.raises(validator.VisualContractValidationError, match="malformed color"):
        validator.validate_visual_contract(contract, _model())


def test_out_of_range_measurement_fails_closed():
    contract = _contract()
    contract["measurements"][0]["value"] = -5
    contract["layout"]["header"]["height_px"] = -5  # keep binding consistent
    with pytest.raises(validator.VisualContractValidationError, match="out-of-range"):
        validator.validate_visual_contract(contract, _model())


def test_unknown_provenance_state_fails_closed():
    contract = _contract()
    contract["measurements"][0]["source_state_id"] = "ghost.state.desktop"
    with pytest.raises(validator.VisualContractValidationError, match="source state"):
        validator.validate_visual_contract(contract, _model())


def test_wrong_artifact_sha_fails_closed():
    contract = _contract()
    contract["measurements"][0]["artifact_sha256"] = "0" * 64
    with pytest.raises(validator.VisualContractValidationError, match="artifact SHA mismatch"):
        validator.validate_visual_contract(contract, _model())


def test_committed_contract_validates_and_is_faithful_ready():
    validated = validator.validate_visual_contract(_contract(), _model())
    assert validator.faithful_ready(validated) is True
    readiness = validated["readiness"]
    assert readiness["missing_required"] == []
    assert readiness["measured_required_count"] == len(
        validator.REQUIRED_MEASURED_FIELDS
    )
    assert readiness["measured_value_count"] >= len(validator.REQUIRED_MEASURED_FIELDS)
    assert readiness["gap_count"] > 0


def test_measurement_provenance_is_exact():
    """Every measurement entry must reference a real state and a matching
    committed artifact (screenshot SHA for pixel_analysis; provenance-manifest
    asset SHA for asset_provenance)."""
    model = _model()
    contract = _contract()
    state_shas = {}
    for state in model["states"]:
        geometry = state.get("document_geometry") or {}
        full = geometry.get("full_page_screenshot") or {}
        if isinstance(full, dict) and full.get("sha256"):
            state_shas[state["state_id"]] = full["sha256"]
    asset_shas = {a.get("sha256") for a in model.get("provenance_manifest", []) or []}
    for entry in contract["measurements"]:
        state_id = entry["source_state_id"]
        assert state_id in state_shas, f"unreferenced provenance state: {state_id}"
        ev_type = entry.get("evidence_type")
        if ev_type == "asset_provenance":
            assert entry["artifact_sha256"] in asset_shas, (
                f"asset SHA not in provenance manifest: {entry['artifact_sha256']}"
            )
            assert entry["field"] == "typography.font_family"
        else:
            assert ev_type == "pixel_analysis"
            assert entry["artifact_sha256"] == state_shas[state_id], (
                f"artifact SHA mismatch for {state_id}: {entry['artifact_sha256']}"
            )
        assert entry.get("unit") is not None or entry["field"] == "typography.font_family"


def test_required_measured_fields_non_null():
    """Every required measured field must be non-null in the committed contract
    (that is what makes faithful_ready True possible)."""
    contract = _contract()
    for field in validator.REQUIRED_MEASURED_FIELDS:
        node = contract
        ok = True
        for part in field.split("."):
            if not isinstance(node, dict) or part not in node or node[part] is None:
                ok = False
                break
            node = node[part]
        assert ok, f"required measured field is null: {field}"


def test_asset_manifest_accounting_exact():
    manifest = json.loads(ASSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    model = _model()
    total = len(model["provenance_manifest"])
    accounting = manifest["accounting"]
    assert accounting["total"] == total == 879
    assert accounting["committed"] == 0
    assert accounting["selected"] == 0
    assert accounting["unresolved"] == total
    assert accounting["review_required"] == total
    assert len(manifest["provenance_entries"]) == total
    assert manifest["committed_assets"] == []
    for entry in manifest["provenance_entries"]:
        assert entry["committed"] is False
        assert entry["local_path"] is None
        assert entry["status"] == "REVIEW_REQUIRED"
    assert manifest["model_checksum"] == validator.compute_model_checksum(model)


def test_asset_manifest_deterministic():
    """The committed manifest equals deterministic regeneration (no sample)."""
    import runpy

    builder = runpy.run_path(str(MEASURE_SCRIPT))
    fresh = builder["build_asset_manifest"]()
    committed = json.loads(ASSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert committed == fresh


# ---------------------------------------------------------------------------
# Evidence 1:1 binding (CTO review 4923712685) — fail-closed negative tests
# ---------------------------------------------------------------------------
def _deepcopy_contract():
    return json.loads(json.dumps(_contract()))


def test_contract_value_tamper_with_evidence_unchanged_fails():
    """Mutating a required contract value while leaving its evidence record
    unchanged must fail (evidence value != contract field value)."""
    contract = _deepcopy_contract()
    contract["layout"]["header"]["height_px"] = 999
    with pytest.raises(validator.VisualContractValidationError, match="field/value mismatch"):
        validator.validate_visual_contract(contract, _model())


def test_evidence_value_tamper_fails():
    """Mutating an evidence value must fail (evidence != contract field)."""
    contract = _deepcopy_contract()
    for entry in contract["measurements"]:
        if entry["field"] == "layout.gnb.height_px":
            entry["value"] = 999
    with pytest.raises(validator.VisualContractValidationError, match="field/value mismatch"):
        validator.validate_visual_contract(contract, _model())


def test_unit_mismatch_fails():
    contract = _deepcopy_contract()
    for entry in contract["measurements"]:
        if entry["field"] == "layout.header.height_px":
            entry["unit"] = "rem"
    with pytest.raises(validator.VisualContractValidationError, match="unit mismatch"):
        validator.validate_visual_contract(contract, _model())


def test_duplicate_field_evidence_fails():
    contract = _deepcopy_contract()
    contract["measurements"].append(
        json.loads(json.dumps(contract["measurements"][0]))
    )
    with pytest.raises(validator.VisualContractValidationError, match="duplicate evidence"):
        validator.validate_visual_contract(contract, _model())


def test_unknown_field_evidence_fails():
    contract = _deepcopy_contract()
    contract["measurements"][0]["field"] = "ghost.field.px"
    with pytest.raises(validator.VisualContractValidationError, match="unknown/unbound"):
        validator.validate_visual_contract(contract, _model())


def test_unbound_evidence_fails():
    """Evidence for a field that does not exist in the contract must fail."""
    contract = _deepcopy_contract()
    contract["measurements"].append({
        "field": "colors.no_such_field",
        "value": "#000000",
        "unit": "hex",
        "evidence_type": "pixel_analysis",
        "source_state_id": "home.desktop.default",
        "artifact_sha256": "e7533aed61bd4d058123abb844d6c580c45625ef3a5720de24b1aed8c0826130",
        "method": "pixel_analysis",
    })
    with pytest.raises(validator.VisualContractValidationError, match="unknown/unbound"):
        validator.validate_visual_contract(contract, _model())


def test_evidence_for_null_field_fails():
    """An evidence record for a contract field whose value is null is a
    field/value mismatch (unbound), not a promotion."""
    contract = _deepcopy_contract()
    contract["measurements"].append({
        "field": "colors.link",
        "value": "#000000",
        "unit": "hex",
        "evidence_type": "pixel_analysis",
        "source_state_id": "home.desktop.default",
        "artifact_sha256": "e7533aed61bd4d058123abb844d6c580c45625ef3a5720de24b1aed8c0826130",
        "method": "pixel_analysis",
    })
    with pytest.raises(validator.VisualContractValidationError, match="field/value mismatch"):
        validator.validate_visual_contract(contract, _model())


def test_required_field_missing_evidence_fails():
    contract = _deepcopy_contract()
    contract["measurements"] = [
        m for m in contract["measurements"] if m["field"] != "layout.header.height_px"
    ]
    with pytest.raises(validator.VisualContractValidationError, match="no evidence"):
        validator.validate_visual_contract(contract, _model())


def test_missing_required_mobile_evidence_fails():
    """Desktop-only evidence must NOT promote a faithful candidate."""
    contract = _deepcopy_contract()
    contract["measurements"] = [
        m for m in contract["measurements"] if not m["field"].startswith("responsive.mobile")
    ]
    with pytest.raises(validator.VisualContractValidationError, match="no evidence"):
        validator.validate_visual_contract(contract, _model())


def test_null_mobile_required_field_cannot_promote():
    contract = _deepcopy_contract()
    contract["responsive"]["mobile"]["header_height_px"] = None
    contract["measurements"] = [
        m for m in contract["measurements"] if m["field"] != "responsive.mobile.header_height_px"
    ]
    # Validator permits the structural contract but readiness must be False.
    validated = validator.validate_visual_contract(contract, _model())
    assert validator.faithful_ready(validated) is False
    assert "responsive.mobile.header_height_px" in validated["readiness"]["missing_required"]


def test_invalid_font_provenance_fails():
    contract = _deepcopy_contract()
    for entry in contract["measurements"]:
        if entry["field"] == "typography.font_family":
            entry["artifact_sha256"] = "deadbeef" * 8
    with pytest.raises(validator.VisualContractValidationError, match="asset artifact SHA mismatch"):
        validator.validate_visual_contract(contract, _model())


def test_font_family_is_asset_provenance_not_pixel():
    """font_family must be represented as asset_provenance evidence, never as
    a screenshot pixel measurement."""
    contract = _deepcopy_contract()
    for entry in contract["measurements"]:
        if entry["field"] == "typography.font_family":
            assert entry["evidence_type"] == "asset_provenance"
            assert entry["method"] == "fetched_font_asset_observation"
            assert entry.get("unit") is None


def test_border_width_must_be_measured_not_guessed():
    """border.width in the committed contract must equal the measured pixel
    thickness (1), and tampering it breaks the evidence binding."""
    contract = _deepcopy_contract()
    assert contract["border"]["width"] == 1
    for entry in contract["measurements"]:
        if entry["field"] == "border.width":
            assert entry["value"] == 1
            assert entry["unit"] == "px"
            assert entry["evidence_type"] == "pixel_analysis"
    # A guessed width (e.g. 3) with unchanged evidence must fail.
    contract["border"]["width"] = 3
    with pytest.raises(validator.VisualContractValidationError, match="field/value mismatch"):
        validator.validate_visual_contract(contract, _model())


# ---------------------------------------------------------------------------
# Evidence source-state binding (CTO review 4923964659 — correction 1)
# ---------------------------------------------------------------------------
def test_mobile_evidence_rejects_desktop_provenance():
    """responsive.mobile.* measurements must originate from the mobile
    provenance state (home.mobile.default), not from a desktop state."""
    contract = _deepcopy_contract()
    model = _model()
    desktop_default = next(
        s for s in model["states"] if s["state_id"] == "home.desktop.default"
    )
    desktop_sha = desktop_default["document_geometry"]["full_page_screenshot"]["sha256"]
    for entry in contract["measurements"]:
        if entry["field"].startswith("responsive.mobile."):
            entry["source_state_id"] = "home.desktop.default"
            # Keep the artifact SHA valid for the desktop state so the test
            # isolates the state-binding check.
            entry["artifact_sha256"] = desktop_sha
    with pytest.raises(
        validator.VisualContractValidationError, match="source state binding violation"
    ):
        validator.validate_visual_contract(contract, model)


def test_desktop_evidence_rejects_wrong_provenance_state():
    """A desktop required field whose evidence references a different valid
    state (even one that exists in the model) must fail."""
    contract = _deepcopy_contract()
    model = _model()
    # Find a required desktop field and move its evidence to a different
    # existing state (home.mobile.default) with that state's valid screenshot SHA.
    mobile_state = next(s for s in model["states"] if s["state_id"] == "home.mobile.default")
    mobile_sha = mobile_state["document_geometry"]["full_page_screenshot"]["sha256"]
    for entry in contract["measurements"]:
        if entry["field"] == "layout.header.height_px":
            entry["source_state_id"] = "home.mobile.default"
            entry["artifact_sha256"] = mobile_sha
    with pytest.raises(
        validator.VisualContractValidationError, match="source state binding violation"
    ):
        validator.validate_visual_contract(contract, model)


# ---------------------------------------------------------------------------
# Provenance gate: required fields MUST have non-null provenance_state_id
# (CTO review 4924580210 — correction 1)
# ---------------------------------------------------------------------------
def test_required_field_provenance_state_id_deleted_fails():
    """Deleting a required field's section provenance_state_id must fail."""
    contract = _deepcopy_contract()
    del contract["layout"]["header"]["provenance_state_id"]
    with pytest.raises(
        validator.VisualContractValidationError, match="provenance_state_id"
    ):
        validator.validate_visual_contract(contract, _model())


def test_required_field_provenance_state_id_null_fails():
    """Setting a required field's section provenance_state_id to null must fail."""
    contract = _deepcopy_contract()
    contract["layout"]["header"]["provenance_state_id"] = None
    with pytest.raises(
        validator.VisualContractValidationError, match="provenance_state_id"
    ):
        validator.validate_visual_contract(contract, _model())


def test_mobile_required_provenance_state_id_deleted_fails():
    """Deleting responsive.mobile.provenance_state_id must fail."""
    contract = _deepcopy_contract()
    del contract["responsive"]["mobile"]["provenance_state_id"]
    with pytest.raises(
        validator.VisualContractValidationError, match="provenance_state_id"
    ):
        validator.validate_visual_contract(contract, _model())


def test_mobile_required_provenance_state_id_null_fails():
    """Setting responsive.mobile.provenance_state_id to null must fail."""
    contract = _deepcopy_contract()
    contract["responsive"]["mobile"]["provenance_state_id"] = None
    with pytest.raises(
        validator.VisualContractValidationError, match="provenance_state_id"
    ):
        validator.validate_visual_contract(contract, _model())


def test_wrong_valid_provenance_state_still_fails():
    """Wrong but existing provenance state + valid SHA must still fail
    (regression — pre-correction behavior preserved)."""
    contract = _deepcopy_contract()
    model = _model()
    mobile_state = next(s for s in model["states"] if s["state_id"] == "home.mobile.default")
    mobile_sha = mobile_state["document_geometry"]["full_page_screenshot"]["sha256"]
    for entry in contract["measurements"]:
        if entry["field"] == "layout.header.height_px":
            entry["source_state_id"] = "home.mobile.default"
            entry["artifact_sha256"] = mobile_sha
    with pytest.raises(
        validator.VisualContractValidationError, match="source state binding violation"
    ):
        validator.validate_visual_contract(contract, model)


# ---------------------------------------------------------------------------
# Ledger evidence rejected (CTO review 4923964659 — correction 2)
# ---------------------------------------------------------------------------
def test_ledger_evidence_rejected():
    """ledger evidence type is not supported in G2-B; any ledger record must
    fail validation."""
    contract = _deepcopy_contract()
    # Change an existing required-field measurement to use ledger type.
    for entry in contract["measurements"]:
        if entry["field"] == "layout.header.height_px":
            entry["evidence_type"] = "ledger"
            entry["artifact_sha256"] = "a" * 64
    with pytest.raises(
        validator.VisualContractValidationError, match="unsupported evidence_type"
    ):
        validator.validate_visual_contract(contract, _model())


def test_null_required_field_cannot_promote():
    contract = _deepcopy_contract()
    contract["colors"]["background"] = None
    contract["measurements"] = [
        m for m in contract["measurements"] if m["field"] != "colors.background"
    ]
    validated = validator.validate_visual_contract(contract, _model())
    assert validator.faithful_ready(validated) is False
    assert "colors.background" in validated["readiness"]["missing_required"]


def test_visual_contract_regeneration_is_deterministic():
    """The measurement tool regenerates the committed contract exactly."""
    result = subprocess.run(
        [sys.executable, str(MEASURE_SCRIPT), "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VISUAL_CONTRACT_OK" in result.stdout
    assert "ASSET_MANIFEST_OK" in result.stdout
