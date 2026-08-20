"""Offline committed-artifact integrity tests for named-site G1 reference capture (#1303).

No network is performed. For every artifact referenced by an executed ledger the
runner hashes the *raw on-disk bytes* of the committed file and asserts the value
matches the ledger-declared SHA-256, and that each screenshot PNG's IHDR
width/height matches the ledger `dimensions`.

Reading bytes raw (open(..., "rb")) is intentional: Git text normalization must
never be applied before hashing, so the committed bytes are the source of truth.
The repo marks these capture paths `-text` in `.gitattributes` so checkouts stay
byte-stable across OSes (including Windows with core.autocrlf=true), which keeps
the ledger SHA-256 equal to the checked-out file bytes.

Plan-awareness:
Each executed ledger declares its own authoritative reference plan via
`plan_identity.path`. The integrity self-contract resolves that path *relative to
the repository root* (rejecting path traversal / repo escape), loads exactly that
plan, and validates the ledger against it with the existing
`validate_reference_capture_contract.validate_ledger()` validator — which retains
plan-id, plan checksum, schema, and G1-completion validation. The set of expected
plan_ids is exact (not an open-ended ``>=`` check) so a missing, unexpected, or
duplicated ledger is a failure.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import socket
import struct
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
G1_CAPTURE_ROOT = REPO_ROOT / "data" / "official_captures" / "seogu_gwangju" / "g1"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_reference_capture_contract.py"

spec = importlib.util.spec_from_file_location("reference_capture_validator", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)

# Exact set of reference plans that the Seo-gu G1 capture family must contain.
# A missing, unexpected, or duplicated plan_id is a contract failure.
EXPECTED_PLAN_IDS = {
    "seogu_gwangju.g1.v1",                 # canonical G2-B capture -> 11 states
    "seogu_gwangju.g1.housing.v1",         # S3 housing capture -> 1 state
    "seogu_gwangju.g1.handoff_evidence.v1",  # S2/S7/S8 evidence capture -> 3 states
    "seogu_gwangju.g1.passport_guidance.v1",  # #1356 S5 passport guidance capture -> 1 state
    "seogu_gwangju.g1.unmanned_kiosk.v1",   # #1360 S6 kiosk catalog capture -> 1 state
}

# Current exact total of committed artifacts across the G1 capture family:
# canonical 11 states * 4 + housing 1 * 4 + handoff evidence 3 * 4
# + passport guidance 1 * 4 + kiosk catalog 1 * 4 = 68.
EXPECTED_ARTIFACT_TOTAL = 68

# Exact successful-state cardinality per plan_id (preserves canonical 11 and the
# additive 1 / 3 / 1 counts; never a loose ``>=``).
EXPECTED_SUCCESS_COUNTS = {
    "seogu_gwangju.g1.v1": 11,
    "seogu_gwangju.g1.housing.v1": 1,
    "seogu_gwangju.g1.handoff_evidence.v1": 3,
    "seogu_gwangju.g1.passport_guidance.v1": 1,
    "seogu_gwangju.g1.unmanned_kiosk.v1": 1,
}

# Populated by load_validated_ledgers(): ledger_path -> loaded reference plan.
PLAN_BY_LEDGER: dict[Path, dict] = {}


@pytest.fixture(autouse=True)
def _no_network():
    """Enforce the offline contract: this test must not touch the network."""
    real_socket = socket.socket

    def _blocked(*_args, **_kwargs):
        raise AssertionError("network access forbidden in offline integrity test")

    socket.socket = _blocked  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = real_socket  # type: ignore[assignment]


def discover_ledgers() -> list[Path]:
    ledgers = sorted(G1_CAPTURE_ROOT.rglob("ledger.json"))
    assert ledgers, f"no executed ledger found under {G1_CAPTURE_ROOT}"
    return ledgers


def resolve_ledger_plan_path(ledger: dict) -> Path:
    """Resolve the ledger's own declared plan path under the repo root.

    Rejects absolute paths and any path traversal / repo escape: the resolved
    file must live strictly inside REPO_ROOT. Raises if the plan file is absent.
    """
    identity = ledger["plan_identity"]
    rel = identity["path"]
    assert isinstance(rel, str) and rel, "ledger.plan_identity.path must be a non-empty string"
    candidate = (REPO_ROOT / rel).resolve() if not Path(rel).is_absolute() else Path(rel).resolve()
    repo_root = REPO_ROOT.resolve()
    # ValueError if candidate is not a descendant of repo_root (path escape guard).
    candidate.relative_to(repo_root)
    assert candidate.is_file(), f"referenced plan file missing or not a file: {candidate}"
    return candidate


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:  # raw bytes; no text normalization
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        signature = handle.read(8)
        assert signature == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
        handle.read(4)  # IHDR chunk length
        assert handle.read(4) == b"IHDR"
        width, height = struct.unpack(">II", handle.read(8))
    return width, height


@pytest.fixture(scope="module")
def ledgers():
    return load_validated_ledgers()


def load_validated_ledgers() -> list[tuple[Path, dict]]:
    out = []
    PLAN_BY_LEDGER.clear()
    for ledger_path in discover_ledgers():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        plan_path = resolve_ledger_plan_path(ledger)
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        # Existing validator enforces plan_id match, plan checksum, schema,
        # state membership, and the G1-completion capture-required gate.
        validator.validate_ledger(ledger, plan, plan_path)
        PLAN_BY_LEDGER[ledger_path] = plan
        out.append((ledger_path, ledger))
    return out


def iter_artifacts(ledger: dict):
    for state in ledger["captured_states"]:
        for artifact in state["artifacts"]:
            yield state, artifact


def test_all_ledgers_reference_exact_plan_set(ledgers):
    discovered = {ledger["plan_identity"]["plan_id"] for _ledger_path, ledger in ledgers}
    assert discovered == EXPECTED_PLAN_IDS, (
        f"G1 capture plan_id set mismatch: discovered {sorted(discovered)} "
        f"!= expected {sorted(EXPECTED_PLAN_IDS)}"
    )


def test_all_artifact_paths_exist(ledgers):
    missing = []
    for _ledger_path, ledger in ledgers:
        for _state, artifact in iter_artifacts(ledger):
            path = REPO_ROOT / artifact["artifact_id"]
            if not path.is_file():
                missing.append(artifact["artifact_id"])
    assert not missing, f"missing committed artifact files: {missing}"


def test_artifact_paths_unique_and_total(ledgers):
    seen: set[str] = set()
    total = 0
    for _ledger_path, ledger in ledgers:
        for _state, artifact in iter_artifacts(ledger):
            artifact_id = artifact["artifact_id"]
            assert artifact_id not in seen, f"duplicate artifact path: {artifact_id}"
            seen.add(artifact_id)
            total += 1
    assert total == EXPECTED_ARTIFACT_TOTAL, (
        f"expected {EXPECTED_ARTIFACT_TOTAL} referenced artifacts, got {total}"
    )


def test_committed_bytes_sha256_matches_ledger(ledgers):
    mismatches = []
    for _ledger_path, ledger in ledgers:
        for _state, artifact in iter_artifacts(ledger):
            path = REPO_ROOT / artifact["artifact_id"]
            actual = sha256_path(path)
            if actual != artifact["sha256"]:
                mismatches.append((artifact["artifact_id"], actual, artifact["sha256"]))
    assert not mismatches, f"committed-byte SHA-256 mismatches: {mismatches}"


def test_screenshot_png_dimensions_match_ledger(ledgers):
    bad = []
    for _ledger_path, ledger in ledgers:
        for _state, artifact in iter_artifacts(ledger):
            if artifact["class"] != "screenshot":
                continue
            path = REPO_ROOT / artifact["artifact_id"]
            width, height = png_dimensions(path)
            dimensions = artifact["dimensions"]
            if width != dimensions["width"] or height != dimensions["height"]:
                bad.append((artifact["artifact_id"], (width, height), (dimensions["width"], dimensions["height"])))
    assert not bad, f"screenshot PNG IHDR dimension mismatches: {bad}"


def test_plan_aware_successful_state_counts(ledgers):
    for ledger_path, ledger in ledgers:
        plan = PLAN_BY_LEDGER[ledger_path]
        plan_index = validator.validate_plan(plan)
        plan_id = ledger["plan_identity"]["plan_id"]
        successful = {s["state_id"] for s in ledger["captured_states"] if s["result_status"] == "success"}
        expected = EXPECTED_SUCCESS_COUNTS[plan_id]
        assert len(successful) == expected, (
            f"{plan_id}: expected {expected} successful states, got {len(successful)}"
        )
        if ledger.get("g1_completion_claim"):
            required = {sid for sid, state in plan_index.items() if state.get("capture_required")}
            assert successful == required, (
                f"{plan_id}: G1 claim requires every capture-required state to succeed"
            )
