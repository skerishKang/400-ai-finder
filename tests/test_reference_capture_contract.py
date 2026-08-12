"""Offline contract tests for named-site Gate G1 reference capture (#1303 Phase A)."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "configs" / "reference-plans" / "seogu_gwangju.json"
PLAN_SCHEMA = REPO_ROOT / "configs" / "platform" / "reference-capture-plan.schema.json"
LEDGER_SCHEMA = REPO_ROOT / "configs" / "platform" / "reference-capture-ledger.schema.json"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_reference_capture_contract.py"

spec = importlib.util.spec_from_file_location("reference_capture_validator", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)

EXPECTED_STATE_IDS = [
    "home.desktop.default",
    "home.mobile.default",
    "home.desktop.gnb_open",
    "notice.list.desktop",
    "notice.detail.desktop",
    "gosi.list.desktop",
    "gosi.detail.desktop",
    "civil_form.list.desktop",
    "civil_form.detail.desktop",
    "organization.chart.desktop",
    "staff.directory.desktop",
]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def base_plan() -> dict:
    return load_json(PLAN_PATH)


def synthetic_artifacts(state: dict) -> list[dict]:
    artifacts = []
    for artifact_class in state["required_artifacts"]:
        artifact = {
            "class": artifact_class,
            "artifact_id": f"synthetic/{state['state_id']}/{artifact_class}",
            "sha256": sha(f"{state['state_id']}:{artifact_class}"),
        }
        if artifact_class == "screenshot":
            artifact["dimensions"] = {"width": state["viewport"]["width"], "height": state["viewport"]["height"] + 10}
        artifacts.append(artifact)
    return artifacts


def synthetic_ledger(*, complete_claim: bool = False) -> dict:
    plan = base_plan()
    captured = []
    for state in plan["states"]:
        captured.append(
            {
                "state_id": state["state_id"],
                "requested_url": state["source_seed_url"],
                "final_url": state["source_seed_url"],
                "captured_at": "2026-08-12T20:00:00+09:00",
                "source_updated_at": None,
                "final_http_status": 200,
                "viewport": copy.deepcopy(state["viewport"]),
                "state": copy.deepcopy(state["state"]),
                "artifacts": synthetic_artifacts(state),
                "public_assets": [],
                "exceptions": [],
                "result_status": "success",
            }
        )
    return {
        "schema_version": "1.0.0",
        "kind": "named_site_reference_capture_ledger",
        "site_id": plan["site_id"],
        "capture_mode": "controlled_read_only_reference",
        "plan_identity": {
            "plan_id": plan["plan_id"],
            "path": "configs/reference-plans/seogu_gwangju.json",
            "sha256": validator.sha256_file(PLAN_PATH),
        },
        "g1_completion_claim": complete_claim,
        "captured_states": captured,
    }


def test_schema_files_are_valid_json_and_fail_closed_at_top_level():
    plan_schema = load_json(PLAN_SCHEMA)
    ledger_schema = load_json(LEDGER_SCHEMA)
    assert plan_schema["additionalProperties"] is False
    assert ledger_schema["additionalProperties"] is False
    assert plan_schema["properties"]["security_boundary"]["additionalProperties"] is False


def test_seogu_plan_is_valid_and_has_exact_declared_states():
    plan = base_plan()
    index = validator.validate_plan(plan)
    assert list(index) == EXPECTED_STATE_IDS
    assert plan["allowed_hosts"] == ["www.seogu.gwangju.kr"]
    assert plan["allowed_methods"] == ["GET"]
    assert plan["routine_ci"] == {"network_policy": "offline"}
    assert plan["completion_policy"]["g1_completion_claim"] is False
    assert plan["completion_policy"]["executed_ledger_required"] is True


def test_detail_seeds_are_freeze_at_capture():
    plan = base_plan()
    states = {state["state_id"]: state for state in plan["states"]}
    for state_id in ("notice.detail.desktop", "gosi.detail.desktop", "civil_form.detail.desktop"):
        assert states[state_id]["freeze_at_capture"] is True


def test_api_eminwon_public_get_seed_is_representable():
    plan = base_plan()
    gosi = next(state for state in plan["states"] if state["state_id"] == "gosi.list.desktop")
    assert "/api/eminwon/" in gosi["source_seed_url"]
    assert validator.validate_plan(plan)


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://www.seogu.gwangju.kr/",
        "https://www.seogu.gwangju.kr.evil.example/",
        "https://www.seogu.gwangju.kr@evil.example/",
        "https://attacker@www.seogu.gwangju.kr/",
    ],
)
def test_bad_seed_urls_are_rejected(bad_url):
    plan = base_plan()
    plan["states"][0]["source_seed_url"] = bad_url
    with pytest.raises(validator.ContractViolation):
        validator.validate_plan(plan)


def test_write_method_is_rejected():
    plan = base_plan()
    plan["allowed_methods"] = ["GET", "POST"]
    with pytest.raises(validator.ContractViolation):
        validator.validate_plan(plan)


def test_duplicate_state_id_is_rejected():
    plan = base_plan()
    plan["states"][1]["state_id"] = plan["states"][0]["state_id"]
    with pytest.raises(validator.ContractViolation):
        validator.validate_plan(plan)


def test_blank_state_id_is_rejected():
    plan = base_plan()
    plan["states"][0]["state_id"] = ""
    with pytest.raises(validator.ContractViolation):
        validator.validate_plan(plan)


@pytest.mark.parametrize("missing_key", ["viewport", "state"])
def test_missing_viewport_or_state_is_rejected(missing_key):
    plan = base_plan()
    del plan["states"][0][missing_key]
    with pytest.raises(validator.ContractViolation):
        validator.validate_plan(plan)


def test_unknown_security_key_is_rejected():
    plan = base_plan()
    plan["security_boundary"]["surprise_write_mode"] = False
    with pytest.raises(validator.ContractViolation):
        validator.validate_plan(plan)


def test_plan_cannot_claim_g1_complete_without_executed_ledger():
    plan = base_plan()
    plan["completion_policy"]["g1_completion_claim"] = True
    with pytest.raises(validator.ContractViolation):
        validator.validate_plan(plan)


def test_synthetic_executed_ledger_contract_can_validate():
    plan = base_plan()
    ledger = synthetic_ledger(complete_claim=True)
    validator.validate_ledger(ledger, plan, PLAN_PATH)


def test_ledger_state_not_in_plan_is_rejected():
    ledger = synthetic_ledger()
    ledger["captured_states"][0]["state_id"] = "unknown.state"
    with pytest.raises(validator.ContractViolation):
        validator.validate_ledger(ledger, base_plan(), PLAN_PATH)


@pytest.mark.parametrize("bad_hash", ["a" * 63, "A" * 64, "not-a-sha"])
def test_malformed_or_nonlowercase_sha256_is_rejected(bad_hash):
    ledger = synthetic_ledger()
    ledger["captured_states"][0]["artifacts"][0]["sha256"] = bad_hash
    with pytest.raises(validator.ContractViolation):
        validator.validate_ledger(ledger, base_plan(), PLAN_PATH)


def test_screenshot_without_dimensions_is_rejected():
    ledger = synthetic_ledger()
    screenshot = next(a for a in ledger["captured_states"][0]["artifacts"] if a["class"] == "screenshot")
    del screenshot["dimensions"]
    with pytest.raises(validator.ContractViolation):
        validator.validate_ledger(ledger, base_plan(), PLAN_PATH)


def test_ledger_viewport_must_match_plan():
    ledger = synthetic_ledger()
    ledger["captured_states"][0]["viewport"]["width"] += 1
    with pytest.raises(validator.ContractViolation):
        validator.validate_ledger(ledger, base_plan(), PLAN_PATH)


def test_plan_ledger_identity_mismatch_is_rejected():
    ledger = synthetic_ledger()
    ledger["plan_identity"]["sha256"] = sha("wrong-plan")
    with pytest.raises(validator.ContractViolation):
        validator.validate_ledger(ledger, base_plan(), PLAN_PATH)


def test_incomplete_ledger_cannot_claim_g1_complete():
    ledger = synthetic_ledger(complete_claim=True)
    ledger["captured_states"].pop()
    with pytest.raises(validator.ContractViolation):
        validator.validate_ledger(ledger, base_plan(), PLAN_PATH)


def test_cli_plan_validation_is_offline_and_does_not_claim_capture_or_g1():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--plan", str(PLAN_PATH)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PLAN_VALID site_id=seogu_gwangju states=11" in result.stdout
    assert "CAPTURE_EXECUTED=NO" in result.stdout
    assert "G1_COMPLETION_CLAIM=NO" in result.stdout
