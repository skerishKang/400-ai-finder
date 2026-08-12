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
PLAN_PATH = REPO_ROOT / "configs" / "reference-plans" / "seogu_gwangju.json"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_reference_capture_contract.py"

spec = importlib.util.spec_from_file_location("reference_capture_validator", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


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
    for ledger_path in discover_ledgers():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        validator.validate_ledger(ledger, plan, PLAN_PATH)
        out.append((ledger_path, ledger))
    return out


def iter_artifacts(ledger: dict):
    for state in ledger["captured_states"]:
        for artifact in state["artifacts"]:
            yield state, artifact


def test_all_ledgers_reference_only_one_capture():
    ledgers = discover_ledgers()
    assert len(ledgers) == 1, f"expected exactly one G1 capture ledger, found {len(ledgers)}"


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
    assert total == 44, f"expected 44 referenced artifacts, got {total}"


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


def test_eleven_successful_states(ledgers):
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    plan_index = validator.validate_plan(plan)
    for _ledger_path, ledger in ledgers:
        successful = {s["state_id"] for s in ledger["captured_states"] if s["result_status"] == "success"}
        assert len(successful) == 11, f"expected 11 successful states, got {len(successful)}"
        if ledger.get("g1_completion_claim"):
            required = {sid for sid, state in plan_index.items() if state.get("capture_required")}
            assert successful == required, "G1 claim requires every capture-required state to succeed"
