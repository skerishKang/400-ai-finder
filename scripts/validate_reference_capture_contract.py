#!/usr/bin/env python3
"""Offline validator for named-site Gate G1 capture plans and executed ledgers.

No network calls are performed. The validator deliberately separates a capture plan from
an executed ledger and refuses to treat a plan alone as Gate G1 completion evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

PLAN_SCHEMA_VERSION = "1.0.0"
LEDGER_SCHEMA_VERSION = "1.0.0"
PLAN_KIND = "named_site_reference_capture_plan"
LEDGER_KIND = "named_site_reference_capture_ledger"
CAPTURE_MODE = "controlled_read_only_reference"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
RFC3339_TZ_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
ARTIFACT_CLASSES = {
    "html_dom_content",
    "screenshot",
    "visible_region_inventory",
    "public_asset_provenance",
}
RESULT_STATUSES = {"success", "partial", "capture_required", "failed"}

PLAN_TOP_KEYS = {
    "schema_version",
    "kind",
    "plan_id",
    "site_id",
    "capture_mode",
    "allowed_hosts",
    "allowed_methods",
    "routine_ci",
    "security_boundary",
    "completion_policy",
    "states",
}
SECURITY_KEYS = {
    "post_allowed",
    "form_submission_allowed",
    "login_allowed",
    "payment_allowed",
    "identity_verification_allowed",
    "pii_entry_allowed",
    "personal_file_upload_allowed",
    "actual_site_mutation_allowed",
}
COMPLETION_KEYS = {
    "g1_completion_claim",
    "executed_ledger_required",
    "uncaptured_state_policy",
}
STATE_KEYS = {
    "state_id",
    "source_seed_url",
    "viewport",
    "state",
    "required_artifacts",
    "freeze_at_capture",
    "capture_required",
    "notes",
}
VIEWPORT_KEYS = {"width", "height"}
STATE_DEF_KEYS = {"name"}
LEDGER_TOP_KEYS = {
    "schema_version",
    "kind",
    "site_id",
    "capture_mode",
    "plan_identity",
    "g1_completion_claim",
    "captured_states",
}
PLAN_IDENTITY_KEYS = {"plan_id", "path", "sha256"}
LEDGER_STATE_KEYS = {
    "state_id",
    "requested_url",
    "final_url",
    "captured_at",
    "source_updated_at",
    "final_http_status",
    "viewport",
    "state",
    "artifacts",
    "public_assets",
    "exceptions",
    "result_status",
}
ARTIFACT_KEYS = {"class", "artifact_id", "sha256", "mime_type", "dimensions"}
ASSET_KEYS = {"source_url", "artifact_id", "sha256", "provenance_note"}
EXCEPTION_KEYS = {"code", "detail"}


class ContractViolation(ValueError):
    """Raised when a plan or ledger violates the fail-closed contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


def _require_exact_keys(obj: object, allowed: set[str], required: set[str], label: str) -> None:
    _require(isinstance(obj, dict), f"{label} must be an object")
    keys = set(obj)
    unknown = keys - allowed
    missing = required - keys
    _require(not unknown, f"{label} contains unknown keys: {sorted(unknown)}")
    _require(not missing, f"{label} missing required keys: {sorted(missing)}")


def _require_nonempty_string(value: object, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{label} must be a non-empty string")
    return value


def _validate_viewport(viewport: object, label: str) -> dict:
    _require_exact_keys(viewport, VIEWPORT_KEYS, VIEWPORT_KEYS, label)
    width = viewport["width"]
    height = viewport["height"]
    _require(isinstance(width, int) and not isinstance(width, bool) and width > 0, f"{label}.width must be a positive integer")
    _require(isinstance(height, int) and not isinstance(height, bool) and height > 0, f"{label}.height must be a positive integer")
    return viewport


def _validate_state_def(state: object, label: str) -> dict:
    _require_exact_keys(state, STATE_DEF_KEYS, STATE_DEF_KEYS, label)
    _require_nonempty_string(state["name"], f"{label}.name")
    return state


def _validate_https_url(url: object, allowed_hosts: set[str], label: str) -> str:
    value = _require_nonempty_string(url, label)
    parsed = urlsplit(value)
    _require(parsed.scheme == "https", f"{label} must use https")
    _require(bool(parsed.netloc), f"{label} must be absolute")
    _require(parsed.username is None and parsed.password is None, f"{label} must not contain userinfo")
    _require(parsed.port is None, f"{label} must not override the port")
    _require(parsed.hostname in allowed_hosts, f"{label} host {parsed.hostname!r} is not exactly allowed")
    _require(not parsed.fragment, f"{label} must not contain a fragment")
    return value


def _validate_sha(value: object, label: str) -> str:
    text = _require_nonempty_string(value, label)
    _require(SHA256_RE.fullmatch(text) is not None, f"{label} must be lowercase 64-hex SHA-256")
    return text


def _validate_timestamp(value: object, label: str, allow_null: bool = False) -> None:
    if allow_null and value is None:
        return
    text = _require_nonempty_string(value, label)
    _require(RFC3339_TZ_RE.fullmatch(text) is not None, f"{label} must be RFC3339 with an explicit timezone")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        doc = json.load(handle)
    _require(isinstance(doc, dict), f"{path} must contain a JSON object")
    return doc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_plan(plan: dict) -> dict[str, dict]:
    _require_exact_keys(plan, PLAN_TOP_KEYS, PLAN_TOP_KEYS, "plan")
    _require(plan["schema_version"] == PLAN_SCHEMA_VERSION, f"plan.schema_version must be {PLAN_SCHEMA_VERSION}")
    _require(plan["kind"] == PLAN_KIND, f"plan.kind must be {PLAN_KIND}")
    _require(ID_RE.fullmatch(_require_nonempty_string(plan["plan_id"], "plan.plan_id")) is not None, "plan.plan_id has invalid characters")
    _require(ID_RE.fullmatch(_require_nonempty_string(plan["site_id"], "plan.site_id")) is not None, "plan.site_id has invalid characters")
    _require(plan["capture_mode"] == CAPTURE_MODE, f"plan.capture_mode must be {CAPTURE_MODE}")

    hosts = plan["allowed_hosts"]
    _require(isinstance(hosts, list) and hosts, "plan.allowed_hosts must be a non-empty array")
    _require(all(isinstance(host, str) and host and host == host.lower() for host in hosts), "plan.allowed_hosts must contain lowercase hostnames")
    _require(len(hosts) == len(set(hosts)), "plan.allowed_hosts must not contain duplicates")
    allowed_hosts = set(hosts)

    _require(plan["allowed_methods"] == ["GET"], "plan.allowed_methods must be exactly ['GET']")

    _require_exact_keys(plan["routine_ci"], {"network_policy"}, {"network_policy"}, "plan.routine_ci")
    _require(plan["routine_ci"]["network_policy"] == "offline", "routine CI network policy must be offline")

    _require_exact_keys(plan["security_boundary"], SECURITY_KEYS, SECURITY_KEYS, "plan.security_boundary")
    for key in SECURITY_KEYS:
        _require(plan["security_boundary"][key] is False, f"plan.security_boundary.{key} must be false")

    _require_exact_keys(plan["completion_policy"], COMPLETION_KEYS, COMPLETION_KEYS, "plan.completion_policy")
    _require(plan["completion_policy"]["g1_completion_claim"] is False, "a capture plan alone must not claim Gate G1 completion")
    _require(plan["completion_policy"]["executed_ledger_required"] is True, "Gate G1 completion requires an executed ledger")
    _require(plan["completion_policy"]["uncaptured_state_policy"] == "capture_required_exception", "uncaptured states must become capture_required exceptions")

    states = plan["states"]
    _require(isinstance(states, list) and states, "plan.states must be a non-empty array")
    indexed: dict[str, dict] = {}
    for idx, state in enumerate(states):
        label = f"plan.states[{idx}]"
        _require_exact_keys(state, STATE_KEYS, STATE_KEYS - {"notes"}, label)
        state_id = _require_nonempty_string(state["state_id"], f"{label}.state_id")
        _require(ID_RE.fullmatch(state_id) is not None, f"{label}.state_id has invalid characters")
        _require(state_id not in indexed, f"duplicate state_id: {state_id}")
        _validate_https_url(state["source_seed_url"], allowed_hosts, f"{label}.source_seed_url")
        _validate_viewport(state["viewport"], f"{label}.viewport")
        _validate_state_def(state["state"], f"{label}.state")
        artifacts = state["required_artifacts"]
        _require(isinstance(artifacts, list) and artifacts, f"{label}.required_artifacts must be non-empty")
        _require(len(artifacts) == len(set(artifacts)), f"{label}.required_artifacts must be unique")
        _require(set(artifacts) <= ARTIFACT_CLASSES, f"{label}.required_artifacts contains unsupported classes")
        _require(isinstance(state["freeze_at_capture"], bool), f"{label}.freeze_at_capture must be boolean")
        _require(isinstance(state["capture_required"], bool), f"{label}.capture_required must be boolean")
        if "notes" in state:
            _require(isinstance(state["notes"], str), f"{label}.notes must be a string")
        indexed[state_id] = state
    return indexed


def _validate_artifact(artifact: object, label: str, viewport: dict) -> str:
    _require_exact_keys(artifact, ARTIFACT_KEYS, {"class", "artifact_id", "sha256"}, label)
    artifact_class = artifact["class"]
    _require(artifact_class in ARTIFACT_CLASSES, f"{label}.class unsupported: {artifact_class!r}")
    _require_nonempty_string(artifact["artifact_id"], f"{label}.artifact_id")
    _validate_sha(artifact["sha256"], f"{label}.sha256")
    if "mime_type" in artifact:
        _require_nonempty_string(artifact["mime_type"], f"{label}.mime_type")
    if artifact_class == "screenshot":
        _require("dimensions" in artifact, f"{label} screenshot requires dimensions")
        _validate_viewport(artifact["dimensions"], f"{label}.dimensions")
        _require(viewport.get("width") and viewport.get("height"), f"{label} screenshot requires viewport context")
    elif "dimensions" in artifact:
        _validate_viewport(artifact["dimensions"], f"{label}.dimensions")
    return artifact_class


def validate_ledger(ledger: dict, plan: dict, plan_path: Path) -> None:
    plan_states = validate_plan(plan)
    _require_exact_keys(ledger, LEDGER_TOP_KEYS, LEDGER_TOP_KEYS, "ledger")
    _require(ledger["schema_version"] == LEDGER_SCHEMA_VERSION, f"ledger.schema_version must be {LEDGER_SCHEMA_VERSION}")
    _require(ledger["kind"] == LEDGER_KIND, f"ledger.kind must be {LEDGER_KIND}")
    _require(ledger["site_id"] == plan["site_id"], "ledger.site_id must match plan.site_id")
    _require(ledger["capture_mode"] == plan["capture_mode"], "ledger.capture_mode must match plan.capture_mode")

    identity = ledger["plan_identity"]
    _require_exact_keys(identity, PLAN_IDENTITY_KEYS, PLAN_IDENTITY_KEYS, "ledger.plan_identity")
    _require(identity["plan_id"] == plan["plan_id"], "ledger plan_id does not match plan")
    _require_nonempty_string(identity["path"], "ledger.plan_identity.path")
    _validate_sha(identity["sha256"], "ledger.plan_identity.sha256")
    _require(identity["sha256"] == sha256_file(plan_path), "ledger plan checksum does not match approved plan bytes")

    _require(isinstance(ledger["g1_completion_claim"], bool), "ledger.g1_completion_claim must be boolean")
    captured_states = ledger["captured_states"]
    _require(isinstance(captured_states, list), "ledger.captured_states must be an array")
    allowed_hosts = set(plan["allowed_hosts"])
    seen: set[str] = set()
    successful: set[str] = set()

    for idx, captured in enumerate(captured_states):
        label = f"ledger.captured_states[{idx}]"
        _require_exact_keys(captured, LEDGER_STATE_KEYS, LEDGER_STATE_KEYS, label)
        state_id = _require_nonempty_string(captured["state_id"], f"{label}.state_id")
        _require(state_id in plan_states, f"ledger state {state_id!r} is not declared in plan")
        _require(state_id not in seen, f"duplicate ledger state_id: {state_id}")
        seen.add(state_id)
        plan_state = plan_states[state_id]

        _validate_https_url(captured["requested_url"], allowed_hosts, f"{label}.requested_url")
        _validate_https_url(captured["final_url"], allowed_hosts, f"{label}.final_url")
        _validate_timestamp(captured["captured_at"], f"{label}.captured_at")
        _validate_timestamp(captured["source_updated_at"], f"{label}.source_updated_at", allow_null=True)
        status = captured["final_http_status"]
        _require(status is None or (isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599), f"{label}.final_http_status must be null or 100..599")
        viewport = _validate_viewport(captured["viewport"], f"{label}.viewport")
        _require(viewport == plan_state["viewport"], f"{label}.viewport must match declared plan viewport")
        state_def = _validate_state_def(captured["state"], f"{label}.state")
        _require(state_def == plan_state["state"], f"{label}.state must match declared plan state")

        artifacts = captured["artifacts"]
        _require(isinstance(artifacts, list), f"{label}.artifacts must be an array")
        classes = set()
        for artifact_idx, artifact in enumerate(artifacts):
            artifact_class = _validate_artifact(artifact, f"{label}.artifacts[{artifact_idx}]", viewport)
            _require(artifact_class not in classes, f"{label} has duplicate artifact class: {artifact_class}")
            classes.add(artifact_class)

        required_classes = set(plan_state["required_artifacts"])
        result_status = captured["result_status"]
        _require(result_status in RESULT_STATUSES, f"{label}.result_status invalid")
        if result_status == "success":
            _require(required_classes <= classes, f"{label} success is missing required artifacts: {sorted(required_classes - classes)}")
            successful.add(state_id)

        assets = captured["public_assets"]
        _require(isinstance(assets, list), f"{label}.public_assets must be an array")
        for asset_idx, asset in enumerate(assets):
            asset_label = f"{label}.public_assets[{asset_idx}]"
            _require_exact_keys(asset, ASSET_KEYS, ASSET_KEYS, asset_label)
            _validate_https_url(asset["source_url"], allowed_hosts, f"{asset_label}.source_url")
            _require_nonempty_string(asset["artifact_id"], f"{asset_label}.artifact_id")
            _validate_sha(asset["sha256"], f"{asset_label}.sha256")
            _require(isinstance(asset["provenance_note"], str), f"{asset_label}.provenance_note must be a string")

        exceptions = captured["exceptions"]
        _require(isinstance(exceptions, list), f"{label}.exceptions must be an array")
        for exc_idx, exc in enumerate(exceptions):
            exc_label = f"{label}.exceptions[{exc_idx}]"
            _require_exact_keys(exc, EXCEPTION_KEYS, EXCEPTION_KEYS, exc_label)
            _require_nonempty_string(exc["code"], f"{exc_label}.code")
            _require_nonempty_string(exc["detail"], f"{exc_label}.detail")

    if ledger["g1_completion_claim"]:
        required_state_ids = {sid for sid, state in plan_states.items() if state["capture_required"]}
        _require(required_state_ids == successful, "Gate G1 completion requires every capture-required plan state to have a successful executed ledger entry")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--ledger", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        plan = load_json(args.plan)
        state_index = validate_plan(plan)
        if args.ledger is None:
            print(f"PLAN_VALID site_id={plan['site_id']} states={len(state_index)}")
            print("CAPTURE_EXECUTED=NO")
            print("G1_COMPLETION_CLAIM=NO")
            return 0
        ledger = load_json(args.ledger)
        validate_ledger(ledger, plan, args.plan)
        print(f"LEDGER_VALID site_id={plan['site_id']} captured_states={len(ledger['captured_states'])}")
        print(f"G1_COMPLETION_CLAIM={'YES' if ledger['g1_completion_claim'] else 'NO'}")
        return 0
    except (OSError, json.JSONDecodeError, ContractViolation) as exc:
        print(f"INVALID_REFERENCE_CAPTURE_CONTRACT: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
