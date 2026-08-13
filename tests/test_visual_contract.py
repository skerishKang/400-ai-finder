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

import importlib.util
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "src" / "official_clone" / "visual_contract.py"
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
    spec = importlib.util.spec_from_file_location("visual_contract", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    with pytest.raises(validator.VisualContractValidationError, match="malformed color"):
        validator.validate_visual_contract(contract, _model())


def test_out_of_range_measurement_fails_closed():
    contract = _contract()
    contract["measurements"][0]["value"] = -5
    with pytest.raises(validator.VisualContractValidationError, match="out-of-range"):
        validator.validate_visual_contract(contract, _model())


def test_unknown_provenance_state_fails_closed():
    contract = _contract()
    contract["measurements"][0]["source_state_id"] = "ghost.state.desktop"
    with pytest.raises(validator.VisualContractValidationError, match="provenance_state_id"):
        validator.validate_visual_contract(contract, _model())


def test_wrong_artifact_sha_fails_closed():
    contract = _contract()
    contract["measurements"][0]["artifact_sha256"] = "0" * 64
    with pytest.raises(validator.VisualContractValidationError, match="artifact_sha256"):
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
    """Every measurement entry must reference a real state and the matching
    committed screenshot SHA recorded in the model's document_geometry."""
    model = _model()
    contract = _contract()
    state_shas = {}
    for state in model["states"]:
        geometry = state.get("document_geometry") or {}
        full = geometry.get("full_page_screenshot") or {}
        if isinstance(full, dict) and full.get("sha256"):
            state_shas[state["state_id"]] = full["sha256"]
    for entry in contract["measurements"]:
        state_id = entry["source_state_id"]
        assert state_id in state_shas, f"unreferenced provenance state: {state_id}"
        assert entry["artifact_sha256"] == state_shas[state_id], (
            f"artifact SHA mismatch for {state_id}: {entry['artifact_sha256']}"
        )
        assert entry.get("method") == "pixel_analysis"


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
