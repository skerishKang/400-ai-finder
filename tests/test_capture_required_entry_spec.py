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
    assert entries, "manifest must contain capture_required entries (13 expected)"
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
    ids = [e["route_id"] for e in manifest.get("capture_required", [])]
    assert "apartment-dept" in ids, "apartment-dept must be a separate capture entry"
    assert "apartment-info" in ids, "apartment-info must be a separate capture entry"
    assert ids.count("apartment-dept") == 1
    assert ids.count("apartment-info") == 1


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
