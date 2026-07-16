"""Minimal documentation consistency contract for Buk-gu golden freeze (#1188).

Locks only high-signal facts shared by the golden compatibility manifest and
clone-first ADR. Intentionally not a full document snapshot test.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GOLDEN_SHA = "7217c0f738a6aa4468bdde3119d8c2d1ec9dd610"
MANIFEST = ROOT / "docs" / "bukgu-golden-compatibility-manifest.md"
ADR = ROOT / "docs" / "architecture" / "clone-first-platform-adr.md"
PHASE_B_NOTES = ROOT / "docs" / "artifacts" / "1145-phase-b" / "phase-b-notes.md"
CANONICAL_EVIDENCE = (
    ROOT / "docs" / "artifacts" / "1109-stage3-comparison" / "comparison-evidence.json"
)
MAP_JS = ROOT / "src" / "web" / "static" / "citizen-action-demo-map.js"

# Claims that must not appear as active golden truth in the new platform docs.
PROHIBITED_GOLDEN_CLAIM_PATTERNS = [
    re.compile(r"\blive-ready\b", re.I),
    re.compile(r"full exact official[- ]site clone of every", re.I),
    re.compile(r"\bactual[- ]site control (?:complete|enabled|ready)\b", re.I),
    re.compile(r"multi-site platform implementation completed", re.I),
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_golden_docs_exist():
    assert MANIFEST.is_file(), f"missing {MANIFEST.relative_to(ROOT)}"
    assert ADR.is_file(), f"missing {ADR.relative_to(ROOT)}"


def test_manifest_and_adr_pin_golden_sha():
    for path in (MANIFEST, ADR):
        text = _read(path)
        assert GOLDEN_SHA in text, f"{path.name} must pin golden SHA {GOLDEN_SHA}"


def test_manifest_and_adr_cross_link():
    manifest = _read(MANIFEST)
    adr = _read(ADR)
    assert "clone-first-platform-adr.md" in manifest
    assert "bukgu-golden-compatibility-manifest.md" in adr


def test_canonical_and_historical_evidence_paths():
    assert CANONICAL_EVIDENCE.is_file()
    assert PHASE_B_NOTES.is_file()
    phase_b = _read(PHASE_B_NOTES)
    assert "1109-stage3-comparison/comparison-evidence.json" in phase_b
    assert "historical" in phase_b.lower() or "Phase A historical" in phase_b

    manifest = _read(MANIFEST)
    assert "1109-stage3-comparison/comparison-evidence.json" in manifest
    assert "1145-phase-a" in manifest
    assert re.search(r"Historical only", manifest, re.I)

    adr = _read(ADR)
    assert "1145-phase-a" in adr
    assert re.search(r"historical only", adr, re.I)


def test_manifest_records_closed_route_count_matching_map():
    map_text = _read(MAP_JS)
    match = re.search(
        r"CLOSED_ROUTE_IDS\s*=\s*Object\.freeze\(\[(.*?)\]\)",
        map_text,
        re.S,
    )
    assert match, "CLOSED_ROUTE_IDS not found in citizen-action-demo-map.js"
    route_ids = re.findall(r'"([^"]+)"', match.group(1))
    assert len(route_ids) == 17, f"expected 17 closed routes, got {len(route_ids)}"

    manifest = _read(MANIFEST)
    assert re.search(r"\b17\b", manifest), "manifest must state closed route count 17"
    for route_id in route_ids:
        assert route_id in manifest, f"manifest missing route id {route_id}"


def test_manifest_states_explicit_non_claims():
    manifest = _read(MANIFEST)
    for fragment in (
        "not a complete exact clone",
        "live LLM",
        "actual Buk-gu site control",
        "real civic submission",
        "live answer-time official retrieval",
    ):
        assert fragment.lower() in manifest.lower(), f"missing non-claim: {fragment}"


def test_platform_docs_avoid_prohibited_overclaim_phrases():
    for path in (MANIFEST, ADR):
        text = _read(path)
        for pattern in PROHIBITED_GOLDEN_CLAIM_PATTERNS:
            # Allow the phrase only when listed as an explicit non-claim.
            for match in pattern.finditer(text):
                window = text[max(0, match.start() - 220) : match.end() + 40].lower()
                line_start = text.rfind("\n", 0, match.start()) + 1
                line = text[line_start : text.find("\n", match.start())].strip().lower()
                allowed = (
                    "is not" in window
                    or "does not" in window
                    or "not mean" in window
                    or "non-claim" in window
                    or "forbidden" in window
                    or "do not" in window
                    or line.startswith("- not ")
                    or line.startswith("* not ")
                    or " not " in line[: line.lower().find(match.group(0).lower()) + 1]
                )
                assert allowed, (
                    f"{path.name} contains overclaim-like phrase "
                    f"{match.group(0)!r} outside a negation window"
                )


def test_adr_states_core_decision_and_deferred_tracks():
    adr = _read(ADR)
    assert "Buk-gu is the first golden reference adapter" in adr
    assert "not permanently Buk-gu-only" in adr
    for issue_token in ("#1080", "#1150", "#862", "#873", "#1181", "Stage 5"):
        assert issue_token in adr, f"ADR must mention deferred/separate track {issue_token}"
