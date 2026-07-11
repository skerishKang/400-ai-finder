"""capture_required entry field-coverage tests (Issue #1078 CTO clarification, pt.5).

Every `capture_required` entry in the manifest MUST carry the 8 mandatory fields
the CTO directive enumerates, plus the structural fields the invariant already
requires. These assertions are strict — no field may be omitted, no entry may
be marked `exact` while only a screenshot/crop/manual-render stub exists.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "official_site_clone_manifest.json"

# The 8 mandatory fields from CTO clarification §5.
REQUIRED_CAPTURE_FIELDS = [
    "route_id",               # route/page ID
    "page_title",             # page title
    "render_target",          # production render target
    "source_url_or_reference",  # official source URL or unconfirmed source reference
    "current_synthetic_location",  # current synthetic/partial/placeholder location
    "missing_official_capture_items",  # lacking official capture items
    "blocking_followup_issue",       # blocking follow-up issue
    "network_required_at_runtime",    # runtime network
]

FORBIDDEN_AS_EXACT = [
    "exact",
    "partial",
    "summary",
    "representative",
    "simplified",
    "approximate",
    "synthetic",
]


def _load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_every_capture_required_entry_has_all_mandatory_fields():
    manifest = _load_manifest()
    entries = manifest.get("capture_required", [])
    assert entries, "manifest must contain capture_required entries"
    for entry in entries:
        rid = entry.get("route_id", "<no route_id>")
        missing = [f for f in REQUIRED_CAPTURE_FIELDS if f not in entry]
        assert not missing, (
            f"capture_required entry '{rid}' missing mandatory fields: {missing}"
        )


def test_capture_required_status_is_capture_required():
    manifest = _load_manifest()
    for entry in manifest.get("capture_required", []):
        rid = entry.get("route_id")
        assert entry.get("status") == "capture_required", (
            f"entry '{rid}' status must be 'capture_required', got {entry.get('status')!r}"
        )


def test_capture_required_entries_are_not_marked_exact():
    manifest = _load_manifest()
    for entry in manifest.get("capture_required", []):
        rid = entry.get("route_id")
        mode = (entry.get("content_mode") or "").lower()
        assert mode not in FORBIDDEN_AS_EXACT, (
            f"entry '{rid}' must not be marked an exact/weak mode while only a "
            f"synthetic/render stub exists; got content_mode={mode!r}"
        )


def test_capture_required_runtime_network_is_false():
    manifest = _load_manifest()
    for entry in manifest.get("capture_required", []):
        rid = entry.get("route_id")
        assert entry.get("network_required_at_runtime") is False, (
            f"entry '{rid}' network_required_at_runtime must be false"
        )


def test_capture_required_without_fixture_is_permitted_but_flagged():
    """capture_required entries legitimately lack a committed fixture_path.

    They MUST carry a current_synthetic_location and a missing_official_capture_items
    note instead of a fabricated fixture_path/content_mode=exact.
    """
    manifest = _load_manifest()
    for entry in manifest.get("capture_required", []):
        rid = entry.get("route_id")
        assert entry.get("current_synthetic_location"), (
            f"entry '{rid}' must record where its synthetic/placeholder render lives"
        )
        assert entry.get("missing_official_capture_items"), (
            f"entry '{rid}' must record which official capture items are missing"
        )
        # A fixture_path may be absent (no complete official fixture yet); that is OK,
        # but it must NOT be a fabricated/non-existent path.
        fp = entry.get("fixture_path")
        if fp:
            from pathlib import Path as _P
            assert _P(ROOT / fp).is_file(), (
                f"entry '{rid}' claims fixture_path {fp} that does not exist"
            )


def test_apartment_dept_and_apartment_info_are_separate_entries():
    manifest = _load_manifest()
    exact_ids = [e["route_id"] for e in manifest.get("pages", [])]
    capture_ids = [e["route_id"] for e in manifest.get("capture_required", [])]
    assert "apartment-dept" in exact_ids, "apartment-dept must be an exact fixture entry"
    assert "apartment-dept" not in capture_ids
    assert "apartment-info" in capture_ids, "apartment-info must remain capture_required"
    assert exact_ids.count("apartment-dept") == 1
    assert capture_ids.count("apartment-info") == 1


def test_capture_required_entry_has_quest_ids_field():
    """§4: each manifest entry may carry a quest_ids mapping field.

    Even empty, the field must be present so the renderer_route → quest_id
    entry-flow mapping is explicit (not implicit/reverse-substituted).
    """
    manifest = _load_manifest()
    for entry in manifest.get("capture_required", []):
        rid = entry.get("route_id")
        assert "quest_ids" in entry, (
            f"entry '{rid}' must carry a 'quest_ids' mapping field (may be empty)"
        )
        assert isinstance(entry["quest_ids"], list), (
            f"entry '{rid}' quest_ids must be a list"
        )


# ---------------------------------------------------------------------------
# Status claim honesty: when capture_required exists, current-status
# documents must not claim clone completion.
# ---------------------------------------------------------------------------

from pathlib import Path as _Path
import re as _re

ROOT_DIR = _Path(__file__).resolve().parents[1]


def _is_status_document(rel: str, text: str) -> bool:
    """Check if a doc is a current-status document by filename or content."""
    low_name = rel.lower()
    status_keywords = [
        "status", "milestone", "snapshot", "closeout",
        "current state", "completion report",
    ]
    if any(kw in low_name for kw in status_keywords):
        return True
    low_text = text.lower()
    # Must mention the current project explicitly
    has_status_signal = any(kw in low_text for kw in status_keywords)
    if not has_status_signal:
        return False
    return True


def _find_status_documents() -> list[str]:
    """Discover current-status documents in the repo."""
    found: list[str] = []
    docs_dir = ROOT_DIR / "docs"
    if not docs_dir.is_dir():
        return found
    for p in docs_dir.rglob("*.md"):
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            rel = p.relative_to(ROOT_DIR).as_posix()
            if _is_status_document(rel, text):
                found.append(rel)
    found.sort()
    return found


# Phrases that claim clone completion — must never appear in a status doc
# when manifest has any capture_required entry.
CLONE_COMPLETE_PHRASES = [
    "clones the official pages verbatim",
    "official clone parity is complete",
    "공식 페이지 그대로 복제가 완료",
    "exact official clone is complete",
    "complete official clone",
]

# Phrases that are allowed — target/goal statements or honest partial status.
ALLOWED_PATTERNS = [
    "Exact clone is the required target.",
    "Official fixture parity remains capture_required.",
    "but official clone parity is not complete.",
    "capture_required",
    "is the target",
]


def _has_clone_complete_claim(text: str) -> list[str]:
    """Find clone-complete claims in text, excluding allowed goal/policy statements."""
    offending: list[str] = []
    low = text.lower()
    for phrase in CLONE_COMPLETE_PHRASES:
        if phrase.lower() in low:
            # Check if this is a goal/policy statement rather than a current-status claim
            # by verifying it's not in the same sentence as allowed patterns
            offending.append(phrase)
    # Remove false positives: claims that are counter-examples or negated
    filtered: list[str] = []
    for phrase in offending:
        # If the phrase is inside a "must not" / "하지 않는다" / "금지" context,
        # it's a prohibition description, not a claim
        low_text = text.lower()
        # Find the sentence containing the phrase
        idx = low_text.index(phrase.lower())
        start = max(0, low_text.rfind("\n", 0, idx))
        end = low_text.find("\n", idx)
        if end == -1:
            end = len(low_text)
        sentence = low_text[start:end]
        prohibition_signals = ["must not", "do not", "never", "금지", "하지 않는다", "불가"]
        allowed_signals = ["requires", "needs", "pending", "incomplete", "not complete"]
        if any(sig in sentence for sig in prohibition_signals):
            continue
        if any(sig in sentence for sig in allowed_signals):
            continue
        filtered.append(phrase)
    return filtered


def _status_detector_positive_self_test():
    """Sentences that MUST be detected as clone-complete claims."""
    must_fail = [
        "The current MVP clones the official pages verbatim.",
        "Official clone parity is complete.",
        "현재 공식 페이지 그대로 복제가 완료되었다.",
    ]
    for s in must_fail:
        violations = _has_clone_complete_claim(s)
        assert violations, (
            f"Status positive self-test failed: should have detected:\n  {s}"
        )


def _status_detector_negative_self_test():
    """Sentences that MUST be allowed."""
    must_pass = [
        "Exact clone is the required target.",
        "Official fixture parity remains capture_required.",
        "The interaction shell is complete, but official clone parity is not complete.",
    ]
    for s in must_pass:
        violations = _has_clone_complete_claim(s)
        assert not violations, (
            f"Status negative self-test failed: should NOT have detected:\n  {s}\n"
            f"Got: {violations}"
        )


def test_status_detector_self_tests():
    _status_detector_positive_self_test()
    _status_detector_negative_self_test()


def test_status_docs_do_not_claim_clone_complete_when_capture_required_exists():
    """When manifest has any capture_required entry, current-status documents
    must not claim the official clone is complete/exact/verbatim."""
    manifest = _load_manifest()
    capture_req = manifest.get("capture_required", [])
    if not capture_req:
        return  # no capture_required means clone may be complete
    status_docs = _find_status_documents()
    assert status_docs, "No status documents found to check"
    for rel in status_docs:
        p = ROOT_DIR / rel
        content = p.read_text(encoding="utf-8", errors="replace")
        violations = _has_clone_complete_claim(content)
        assert not violations, (
            f"{rel} claims clone completion while capture_required entries exist: "
        + " || ".join(violations)
    )


# ---------------------------------------------------------------------------
# Product-transition classification contract (Issue #1096)
# ---------------------------------------------------------------------------

PRODUCT_TRANSITION_ROUTES = [
    "complaint-board",
    "complaint-write",
    "complaint-review",
    "handoff-stop",
    "mayor-office",
    "mayor-complaint-write",
    "mayor-complaint-receipt",
]

FORBIDDEN_PROVENANCE_FIELDS = [
    "source_url",
    "source_url_or_reference",
    "fixture_path",
    "snapshot_id",
    "canonical_sha256",
    "captured_at",
    "verified_at",
    "source_updated_at",
    "content_mode",
]


def _load_product_transitions() -> list:
    manifest = _load_manifest()
    return manifest.get("product_transitions", [])


def test_product_transitions_section_exists():
    manifest = _load_manifest()
    assert "product_transitions" in manifest, "manifest must define product_transitions section"


def test_product_transitions_contains_registered_routes():
    ids = [e["route_id"] for e in _load_product_transitions()]
    assert sorted(ids) == sorted(PRODUCT_TRANSITION_ROUTES), (
        f"product_transitions must contain exactly {PRODUCT_TRANSITION_ROUTES}, got {ids}"
    )


def test_product_transition_entries_appear_once_each():
    ids = [e["route_id"] for e in _load_product_transitions()]
    dupes = {rid for rid in ids if ids.count(rid) > 1}
    assert not dupes, f"duplicate product_transition route_id(s): {dupes}"


def test_product_transitions_have_required_classification_fields():
    for e in _load_product_transitions():
        rid = e.get("route_id")
        assert e.get("surface_kind") == "product_transition", (
            f"{rid} surface_kind must be 'product_transition'"
        )
        assert e.get("official_capture_expectation") == "not_applicable", (
            f"{rid} official_capture_expectation must be 'not_applicable'"
        )
        assert e.get("status") == "product_transition", (
            f"{rid} status must be 'product_transition'"
        )
        assert e.get("network_required_at_runtime") is False, (
            f"{rid} network_required_at_runtime must be false"
        )
        contract = e.get("product_state_contract")
        assert isinstance(contract, dict) and contract, (
            f"{rid} must carry a non-empty product_state_contract dict"
        )


def test_product_transitions_forbid_official_provenance():
    for e in _load_product_transitions():
        rid = e.get("route_id")
        for field in FORBIDDEN_PROVENANCE_FIELDS:
            assert field not in e, (
                f"{rid} must not carry official provenance field '{field}'"
            )
        assert e.get("status") != "exact", f"{rid} must not be status exact"


def test_product_transitions_disjoint_from_other_sections():
    manifest = _load_manifest()
    pt_ids = {e["route_id"] for e in manifest.get("product_transitions", [])}
    page_ids = {e["route_id"] for e in manifest.get("pages", [])}
    cap_ids = {e["route_id"] for e in manifest.get("capture_required", [])}
    complete = set(manifest.get("complete_capture_required", []))
    assert not (pt_ids & page_ids), f"product_transitions overlaps pages: {pt_ids & page_ids}"
    assert not (pt_ids & cap_ids), f"product_transitions overlaps capture_required: {pt_ids & cap_ids}"
    assert not (pt_ids & complete), f"product_transitions overlaps complete_capture_required: {pt_ids & complete}"
