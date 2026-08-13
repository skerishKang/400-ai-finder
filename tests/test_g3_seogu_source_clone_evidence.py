"""G3 Phase 1 evidence integrity tests for the Seo-gu source-vs-clone review.

Fail-closed, offline assertions over the *committed* evidence set only:
  * candidate SHA matches the exact reviewed main commit;
  * exactly 11 states in the canonical deterministic ordering (no missing/extra);
  * every committed G1 source.png SHA-256 == manifest == G1 ledger
    (wrong candidate SHA / wrong source checksum fail closed);
  * every clone + side-by-side artifact present with matching SHA-256
    (missing screenshot / side-by-side / SHA mismatch fail closed);
  * per-state viewport matches the G1 capture viewport (viewport mismatch
    fail closed);
  * external network count == 0 (external network nonzero fail closed);
  * lifecycle gates remain closed (visual_review=pending,
    owner_visual_approved=false, asset_byte_fidelity_complete=false).

No network, no live site, no provider/API.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_COMMIT_SHA = "2be1b85e04cc755255298ad94eb68934adf0da40"
G1_CAPTURE_ID = "20260812T231018-0900"
SITE_ID = "seogu_gwangju"

EVIDENCE_ROOT = (
    REPO_ROOT
    / "data"
    / "official_clone_reviews"
    / SITE_ID.split("_")[0]
    / "g3"
    / CANDIDATE_COMMIT_SHA
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Source parity is grounded in committed G1 evidence, fail-closed. These are the
# known material gaps that MUST NOT be reported as source-parity PASS (the source
# is demonstrably richer than the modeled clone).
_SCRIPT_PATH = REPO_ROOT / "scripts" / "g3_seogu_source_clone_review.py"
_g3_spec = importlib.util.spec_from_file_location(
    "g3_seogu_source_clone_review", str(_SCRIPT_PATH))
g3 = importlib.util.module_from_spec(_g3_spec)
_g3_spec.loader.exec_module(g3)
KNOWN_GAP_STATES = set(g3.KNOWN_SOURCE_PARITY_GAPS)

# Canonical deterministic 11-state ordering (matches tests/REQUIRED_11 and the
# G1 capture plan). Tuples: (state_id, viewport, canonical_clone_route).
EXPECTED_STATES = [
    ("home.desktop.default",        {"width": 1440, "height": 900}, "/seogu/"),
    ("home.mobile.default",         {"width": 390,  "height": 844}, "/seogu/home/mobile/"),
    ("home.desktop.gnb_open",       {"width": 1440, "height": 900}, "/seogu/home/gnb-open/"),
    ("notice.list.desktop",         {"width": 1440, "height": 900}, "/seogu/notice/"),
    ("notice.detail.desktop",       {"width": 1440, "height": 900}, "/seogu/notice/detail/"),
    ("gosi.list.desktop",           {"width": 1440, "height": 900}, "/seogu/gosi/"),
    ("gosi.detail.desktop",         {"width": 1440, "height": 900}, "/seogu/gosi/detail/"),
    ("civil_form.list.desktop",     {"width": 1440, "height": 900}, "/seogu/civil-form/"),
    ("civil_form.detail.desktop",   {"width": 1440, "height": 900}, "/seogu/civil-form/detail/"),
    ("organization.chart.desktop",  {"width": 1440, "height": 900}, "/seogu/organization/"),
    ("staff.directory.desktop",     {"width": 1440, "height": 900}, "/seogu/staff/"),
]
EXPECTED_ORDER = [s[0] for s in EXPECTED_STATES]
EXPECTED_VIEWPORTS = {s[0]: s[1] for s in EXPECTED_STATES}
EXPECTED_ROUTES = {s[0]: s[2] for s in EXPECTED_STATES}

CAPTURE_ROOT = (
    REPO_ROOT
    / "data"
    / "official_captures"
    / SITE_ID
    / "g1"
    / G1_CAPTURE_ID
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def manifest() -> dict:
    assert (EVIDENCE_ROOT / "manifest.json").is_file(), "manifest.json missing"
    return json.loads((EVIDENCE_ROOT / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ledger() -> dict:
    return json.loads((CAPTURE_ROOT / "ledger.json").read_text(encoding="utf-8"))


def test_candidate_sha_is_exact_main(manifest):
    # wrong candidate SHA -> fail closed
    assert manifest["candidate_commit_sha"] == CANDIDATE_COMMIT_SHA


def test_g1_capture_id(manifest):
    assert manifest["g1_capture_id"] == G1_CAPTURE_ID


def test_evidence_root_path_shape(manifest):
    assert manifest["evidence_root"].replace("\\", "/") == (
        "data/official_clone_reviews/seogu/g3/" + CANDIDATE_COMMIT_SHA
    )


def test_evidence_root_has_only_allowlisted_entries():
    expected_files = set()
    for sid, _, _ in EXPECTED_STATES:
        expected_files.add(f"states/{sid}/clone.png")
        expected_files.add(f"states/{sid}/side_by_side.png")
    expected_files.add("manifest.json")
    expected_files.add("review.md")
    actual = {
        str(p.relative_to(EVIDENCE_ROOT).as_posix())
        for p in EVIDENCE_ROOT.rglob("*")
        if p.is_file()
    }
    assert actual == expected_files, (
        f"evidence root membership mismatch: extra={sorted(actual-expected_files)} "
        f"missing={sorted(expected_files-actual)}"
    )


def test_exactly_11_states_no_missing_no_extra(manifest):
    ids = [s["state_id"] for s in manifest["states"]]
    assert len(manifest["states"]) == 11
    assert ids == EXPECTED_ORDER


def test_external_network_zero_total(manifest):
    # external network nonzero -> fail closed
    assert manifest["external_network_total"] == 0
    assert all(s["external_network_count"] == 0 for s in manifest["states"])


def test_lifecycle_gates_remain_closed(manifest):
    life = manifest["lifecycle"]
    # evidence complete (all 11 present + net zero) but no promotion gate.
    assert life["g3_evidence_complete"] is True
    assert life["visual_review"] == "pending"
    assert life["owner_visual_approved"] is False
    assert life["clone_mvp_ready"] is False
    assert life["exact"] is False
    assert life["golden"] is False
    assert life["resident_default"] is False
    assert life["production_ready"] is False
    assert life["actual_site_integrated"] is False
    assert life["asset_byte_fidelity_complete"] is False


@pytest.mark.parametrize("state_id,viewport,route", EXPECTED_STATES)
def test_state_artifact_integrity(manifest, ledger, state_id, viewport, route):
    states = {s["state_id"]: s for s in manifest["states"]}
    rec = states[state_id]

    # route / viewport parity (viewport mismatch -> fail closed)
    assert rec["clone_route"] == route
    assert rec["capture_viewport"] == viewport
    assert rec["source_viewport"] == viewport

    # source path + SHA (wrong source checksum -> fail closed)
    src_rel = rec["source_screenshot_path"]
    assert src_rel.replace("\\", "/").startswith(
        f"data/official_captures/seogu_gwangju/g1/{G1_CAPTURE_ID}/states/{state_id}/source.png"
    )
    src_path = REPO_ROOT / src_rel
    assert src_path.is_file(), f"source.png missing: {src_path}"
    file_sha = _sha256(src_path)
    assert rec["source_screenshot_sha256"] == file_sha, "manifest source SHA != file"
    assert file_sha == _ledger_source_sha(ledger, state_id), "file SHA != G1 ledger SHA"

    # clone screenshot (missing clone -> fail closed)
    clone_rel = rec["clone_screenshot_path"]
    clone_path = REPO_ROOT / clone_rel
    assert clone_path.is_file(), f"clone screenshot missing: {clone_path}"
    clone_data = clone_path.read_bytes()
    assert clone_data[:8] == PNG_MAGIC, "clone screenshot not a valid PNG"
    assert _sha256(clone_path) == rec["clone_screenshot_sha256"], "manifest clone SHA != file"

    # side-by-side (missing side-by-side -> fail closed; SHA mismatch -> fail closed)
    sbs_rel = rec["side_by_side_path"]
    sbs_path = REPO_ROOT / sbs_rel
    assert sbs_path.is_file(), f"side-by-side missing: {sbs_path}"
    sbs_data = sbs_path.read_bytes()
    assert sbs_data[:8] == PNG_MAGIC, "side-by-side not a valid PNG"
    assert _sha256(sbs_path) == rec["side_by_side_sha256"], "manifest side-by-side SHA != file"

    # per-state external network (nonzero -> fail closed)
    assert rec["external_network_count"] == 0
    assert rec["external_requests"] == []

    # gnb-open state captured with GNB actually open
    if state_id == "home.desktop.gnb_open":
        g = rec["gnb_open_state"]
        assert g is not None
        assert g["aria_expanded"] == "true"
        assert g["panel_visible"] is True


def _ledger_source_sha(ledger: dict, state_id: str) -> str:
    for s in ledger["captured_states"]:
        if s["state_id"] == state_id:
            png = next((a for a in s["artifacts"] if a.get("class") == "screenshot"), None)
            assert png is not None, f"ledger has no screenshot for {state_id}"
            return png["sha256"]
    raise AssertionError(f"ledger missing state {state_id}")


def test_review_md_exists_and_documents_closures():
    review = EVIDENCE_ROOT / "review.md"
    assert review.is_file(), "review.md missing"
    text = review.read_text(encoding="utf-8")
    assert "visual_review=pending" in text
    assert "owner_visual_approved=false" in text
    assert "asset_byte_fidelity_complete=false" in text
    # 11-state matrix present
    for sid, _, _ in EXPECTED_STATES:
        assert f"`{sid}`" in text


def test_source_parity_not_all_pass(manifest):
    # Regression guard: the generator must NOT blanket-PASS all 11 states'
    # source structural/content. At least one state must be non-PASS.
    states = manifest["states"]
    assert len(states) == 11
    all_structural_pass = all(s["source_parity"]["structural"] == "PASS" for s in states)
    all_content_pass = all(s["source_parity"]["content"] == "PASS" for s in states)
    assert not all_structural_pass, "source parity structural is ALL PASS (blanket PASS)"
    assert not all_content_pass, "source parity content is ALL PASS (blanket PASS)"


def test_modeled_contract_separate_from_source_parity(manifest):
    # modeled_contract (clone QA) and source_parity (G1 grounded) must be
    # distinct fields/sections, not reused.
    states = {s["state_id"]: s for s in manifest["states"]}
    for sid, s in states.items():
        assert "modeled_contract" in s, f"{sid}: missing modeled_contract"
        assert "source_parity" in s, f"{sid}: missing source_parity"
        mc = s["modeled_contract"]
        sp = s["source_parity"]
        assert mc is not None and sp is not None
        assert mc is not sp, f"{sid}: modeled_contract and source_parity share object"
        assert set(mc.keys()) != set(sp.keys()), f"{sid}: field sets identical"
    # The set of known gaps must match the canonical 8.
    reported_gaps = {s["state_id"] for s in manifest["states"] if s["source_parity"]["gap"]}
    assert reported_gaps == KNOWN_GAP_STATES, (
        f"known-gap set drift: reported={sorted(reported_gaps)} "
        f"expected={sorted(KNOWN_GAP_STATES)}"
    )


def test_known_gaps_not_source_parity_pass(manifest):
    # Requirement: the 8 known material gaps must NOT be source structural/content PASS.
    states = {s["state_id"]: s for s in manifest["states"]}
    for sid in KNOWN_GAP_STATES:
        sp = states[sid]["source_parity"]
        assert sp["gap"] is True, f"{sid}: not flagged as gap"
        assert sp["structural"] != "PASS", f"{sid}: source structural PASS (forbidden)"
        assert sp["content"] != "PASS", f"{sid}: source content PASS (forbidden)"
        assert sp["reason"], f"{sid}: missing gap reason/exception"
        # direction must be DIFFER (source richer) — conservative, never relaxed to PASS.
        assert sp["structural"] == "DIFFER"
        assert sp["content"] == "DIFFER"


def test_source_parity_asset_visual_conservative(manifest):
    # Conservative states must remain FAIL/DIFFER; never relaxed to PASS.
    for s in manifest["states"]:
        sp = s["source_parity"]
        assert sp["asset"] == "FAIL", "asset must remain FAIL"
        assert sp["visual"] == "DIFFER", "visual must remain DIFFER"


def test_review_md_separates_modeled_contract_and_source_parity():
    review = EVIDENCE_ROOT / "review.md"
    assert review.is_file(), "review.md missing"
    text = review.read_text(encoding="utf-8")
    # Distinct sections present.
    assert "## Modeled contract (clone offline QA" in text
    assert "## Source parity (G1 committed evidence grounded)" in text
    # No blanket modeled-contract PASS reused as source parity.
    assert "modeled-contract PASS is NOT source-parity PASS" in text
    # Known gaps documented as DIFFER with reasons.
    for sid in KNOWN_GAP_STATES:
        assert f"`{sid}`" in text
    assert "KNOWN GAP (source richer than clone)" in text


def test_responsive_not_auto_derived_from_gap(manifest):
    # Requirement: responsive must NOT be auto-derived from a structural/content
    # gap. It is decided only by the separate RESPONSIVE_PARITY_EVIDENCE mapping,
    # which currently has no positive source-vs-clone responsive evidence, so
    # every state is fail-closed NOT_ASSESSED.
    states = {s["state_id"]: s for s in manifest["states"]}
    for sid, s in states.items():
        sp = s["source_parity"]
        # No state may report responsive=DIFFER purely because it is a gap.
        if sp["gap"]:
            assert sp["responsive"] != "DIFFER", (
                f"{sid}: responsive must not auto-DIFFER from structural/content gap")
        # Desktop-only states (no cross-viewport evidence) must be NOT_ASSESSED.
        assert sp["responsive"] == "NOT_ASSESSED", (
            f"{sid}: responsive requires separate evidence mapping; got {sp['responsive']}")
    # Explicit guard for the listed desktop-only states.
    for sid in ("notice.detail.desktop", "gosi.detail.desktop",
                "civil_form.detail.desktop", "organization.chart.desktop",
                "staff.directory.desktop"):
        assert states[sid]["source_parity"]["responsive"] == "NOT_ASSESSED"
    # Mapping source of truth is the separate evidence dict (empty => all N/A).
    assert g3.RESPONSIVE_PARITY_EVIDENCE == {}, "responsive mapping must stay empty until evidence exists"

