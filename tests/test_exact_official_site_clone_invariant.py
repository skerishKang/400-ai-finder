"""Exact official-site clone invariant contract tests (Issue #1078).

Locks the repository-wide invariant that the LEFT civic-site surface is a verbatim
clone of the official Gwangju Buk-gu portal (https://bukgu.gwangju.kr). No summary,
abbreviation, simplification, redesign, or approximation of the official page is
permitted. This test enforces the canonical invariant document and the official
page fixture manifest.

This test deliberately does NOT weaken assertions, skip, or xfail.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DOC = "docs/product/exact-official-site-clone-invariant.md"
CANONICAL_LINK_TEXT = "exact-official-site-clone-invariant.md"
MANIFEST = ROOT / "tests" / "fixtures" / "official_site_clone_manifest.json"

# Clone-relevant documents that MUST reference the canonical invariant and MUST NOT
# contain a sentence that APPROVES a weak (summary / approximate / redesigned) direction.
#
# Dynamically discovered: every non-binary Markdown file under docs/ and the root
# README.md that either (a) contains a link to the canonical invariant or (b) is
# the canonical invariant document itself.  No hand-maintained literal replaces
# this scan so newly created clone-relevant documents are automatically covered.
DOC_PATTERNS = ("*.md", "*.mdx")
_EXCLUDED_ROOTS = frozenset({
    ".claude", ".git", "node_modules", "__pycache__", ".pytest_cache",
    "data", "dist", "extensions", "presentation", "proposal", "prompts",
    "examples", "tools",
})


def _discover_clone_related_docs() -> list[str]:
    """Walk the repository and collect docs referencing the canonical invariant.

    No hand-maintained literal replaces this scan, so newly created clone-relevant
    documents are automatically covered.
    """
    found: list[str] = []
    found.append(CANONICAL_DOC)
    readme_path = ROOT / "README.md"
    if readme_path.is_file():
        found.append("README.md")
    docs_dir = ROOT / "docs"
    if docs_dir.is_dir():
        for pattern in DOC_PATTERNS:
            for p in docs_dir.rglob(pattern):
                if any(excluded in p.parts for excluded in _EXCLUDED_ROOTS):
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                if CANONICAL_LINK_TEXT in text or CANONICAL_DOC in text:
                    rel = p.relative_to(ROOT).as_posix()
                    if rel not in found:
                        found.append(rel)
    found.sort()
    return found


CLONE_RELATED_DOCS = _discover_clone_related_docs()

OFFICIAL_DOMAIN = "https://bukgu.gwangju.kr"

# Forbidden explicit phrases — must never appear in clone-relevant docs, regardless of
# surrounding approval language. These encode the directions that are permanently banned.
FORBIDDEN_PHRASES = [
    "high-fidelity",
    "high fidelity",
    "closely enough",
    "고충실도",
    "대표 행",
    "대표행",
    "요약 화면",
    "간소 버전",
    "간소버전",
    "demo-quality reproduction",
    "demo quality reproduction",
    "representative rows",
    "representative row",
    "Use a summary instead of the official page",
    "Use a summary instead",
    "summary instead of official",
]

# Weak terms whose mere presence is not a violation, but which become a violation when a
# sentence ALSO contains an approval/permission signal (the sentence approves a weak clone).
# Note: rebuild verbs (reconstruct / 재구성 / 재현 / recreate) are intentionally EXCLUDED —
# they are neutral "rebuild verbatim" verbs, not weak directions by themselves.
WEAK_TERMS = [
    "요약", "축약", "간소", "재설계", "근사", "유사", "비슷",
    "approximate", "approximation", "representative", "summary", "simplified",
    "simplify", "simulation", "simulated", "inspired by",
    "approximately", "근접", "충분히 유사",
]

# Approval / permission signals: a sentence that contains a weak term AND one of these
# approves a weak direction (e.g. "representative rows are shown", "approximately 910px",
# "high-fidelity reconstruction"). Rebuild verbs are NOT here (see WEAK_TERMS note).
APPROVAL_SIGNALS = [
    "허용", "가능", "수준", "대신", "instead", "acceptable", "enough", "충분",
    "근접", "비슷", "유사", "approximate", "approximation", "closely",
    "보여", "표시", "노출", "사용", "적용",
    "는다", "한다", "이다", "입니다", "있습니다",
]


def _split_sentences(text: str) -> list[str]:
    # Naive sentence splitter good enough for doc scanning.
    parts = re.split(r"(?<=[.。!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


# Explicit negation signals — a sentence that forbids a weak direction is the OPPOSITE
# of approving it, and must NOT be flagged.
NEGATION_SIGNALS = [
    "하지 않", "하지 않", "않", "금지", "금지하", "금지되", "must not", "no ", "not ",
    "절대", "禁止", "forbidden", "disallow", "cannot", "can't", "never", "없",
    "없이", "instead of", "대신", " molten", "불가", "안 ", "안 되", "되지 않",
]


def _has_weak_approval_sentence(text: str) -> list[str]:
    """Return list of offending sentences (weak term + approval signal, NOT negated)."""
    offending: list[str] = []
    for sent in _split_sentences(text):
        low = sent.lower()
        has_weak = any(w.lower() in low for w in WEAK_TERMS)
        if not has_weak:
            continue
        # Skip sentences that explicitly FORBID the weak direction.
        if any(neg in low for neg in NEGATION_SIGNALS):
            continue
        has_approval = any(s.lower() in low for s in APPROVAL_SIGNALS)
        if has_approval:
            offending.append(sent)
    return offending


# ---------------------------------------------------------------------------
# 1. canonical invariant document exists
# ---------------------------------------------------------------------------

def test_canonical_invariant_document_exists():
    assert (ROOT / CANONICAL_DOC).is_file(), (
        f"canonical invariant doc missing: {CANONICAL_DOC}"
    )


# ---------------------------------------------------------------------------
# 2. primary README links the canonical document
# ---------------------------------------------------------------------------

def test_readme_links_canonical_invariant():
    readme = ROOT / "README.md"
    assert readme.is_file()
    content = readme.read_text(encoding="utf-8")
    assert CANONICAL_LINK_TEXT in content, (
        "README must link the canonical exact-official-site-clone invariant doc"
    )
    # The required invariant sentence must be present verbatim (or its English form).
    required_ko = (
        "왼쪽 시민 사이트 화면은 캡처된 광주광역시 북구청 공식 페이지를 그대로 복제한다"
    )
    required_en = (
        "The left civic-site surface clones the captured official Gwangju Buk-gu "
        "portal page verbatim"
    )
    assert required_ko in content or required_en in content, (
        "README must state the exact-clone invariant sentence verbatim"
    )


# ---------------------------------------------------------------------------
# 3. clone-related docs link the canonical document
# ---------------------------------------------------------------------------

def test_clone_related_docs_link_canonical():
    for rel in CLONE_RELATED_DOCS:
        p = ROOT / rel
        assert p.is_file(), f"clone-related doc missing: {rel}"
        # The canonical doc itself is the reference; skip self-link check.
        if rel == CANONICAL_DOC:
            continue
        content = p.read_text(encoding="utf-8")
        assert CANONICAL_LINK_TEXT in content or CANONICAL_DOC in content, (
            f"{rel} must reference the canonical invariant doc ({CANONICAL_DOC})"
        )


# ---------------------------------------------------------------------------
# 4. clone-related docs contain no sentence that approves a weak direction
# ---------------------------------------------------------------------------

def test_clone_related_docs_have_no_weak_approval_language():
    for rel in CLONE_RELATED_DOCS:
        p = ROOT / rel
        content = p.read_text(encoding="utf-8")
        # The canonical invariant doc itself enumerates forbidden phrases as examples to
        # BLOCK; skip both the hard-block phrase scan and the weak-approval detector on it.
        if rel == CANONICAL_DOC:
            continue
        # Hard-blocked explicit phrases (any occurrence is a violation).
        low = content.lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase.lower() not in low, (
                f"{rel} contains forbidden clone-weakening phrase: '{phrase}'"
            )
        # Sentence-level weak-approval detection.
        offending = _has_weak_approval_sentence(content)
        assert not offending, (
            f"{rel} contains sentence(s) that approve a weak (non-exact) clone direction: "
            + " || ".join(offending)
        )


# ---------------------------------------------------------------------------
# 5. official page fixture manifest exists
# ---------------------------------------------------------------------------

def test_official_page_fixture_manifest_exists():
    assert MANIFEST.is_file(), (
        f"official page fixture manifest missing: {MANIFEST}"
    )


# ---------------------------------------------------------------------------
# 6. every manifest entry has required source metadata
# ---------------------------------------------------------------------------

REQUIRED_ENTRY_FIELDS = [
    "page_id",
    "route_id",
    "page_title",
    "source_url",
    "captured_at",
    "verified_at",
    "source_updated_at",
    "fixture_path",
    "render_target",
    "content_mode",
    "network_required_at_runtime",
]


def _load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_entries_have_required_source_metadata():
    manifest = _load_manifest()
    pages = manifest.get("pages", [])
    for entry in pages:
        missing = [f for f in REQUIRED_ENTRY_FIELDS if f not in entry]
        assert not missing, (
            f"manifest page {entry.get('page_id')} missing fields: {missing}"
        )


# ---------------------------------------------------------------------------
# 7. source URL is the official Buk-gu public domain
# ---------------------------------------------------------------------------

def test_manifest_source_urls_official_domain():
    manifest = _load_manifest()
    for entry in manifest.get("pages", []):
        url = entry.get("source_url", "")
        assert url.startswith(OFFICIAL_DOMAIN), (
            f"manifest page {entry.get('page_id')} source_url not under "
            f"{OFFICIAL_DOMAIN}: {url}"
        )


# ---------------------------------------------------------------------------
# 8. fixture path exists
# ---------------------------------------------------------------------------

def test_manifest_fixture_paths_exist():
    manifest = _load_manifest()
    for entry in manifest.get("pages", []):
        fixture_path = entry.get("fixture_path")
        assert fixture_path, f"page {entry.get('page_id')} has no fixture_path"
        assert (ROOT / fixture_path).is_file(), (
            f"fixture file missing for page {entry.get('page_id')}: {fixture_path}"
        )


# ---------------------------------------------------------------------------
# 9. fixture does not allow partial/summary/representative/simplified/approximate
# ---------------------------------------------------------------------------

FORBIDDEN_CONTENT_MODES = [
    "partial",
    "summary",
    "representative",
    "simplified",
    "approximate",
    "synthetic",
]


def test_manifest_forbids_weak_content_modes():
    manifest = _load_manifest()
    declared = manifest.get("forbidden_content_modes", [])
    for mode in FORBIDDEN_CONTENT_MODES:
        assert mode in declared, (
            f"manifest must declare '{mode}' as a forbidden content_mode"
        )
    for entry in manifest.get("pages", []):
        mode = (entry.get("content_mode") or "").lower()
        assert mode not in FORBIDDEN_CONTENT_MODES, (
            f"page {entry.get('page_id')} uses forbidden content_mode: {mode}"
        )


# ---------------------------------------------------------------------------
# 10. no duplicate source-of-truth for the same route/page
# ---------------------------------------------------------------------------

def test_manifest_no_duplicate_source_of_truth():
    manifest = _load_manifest()
    seen = set()
    for entry in manifest.get("pages", []):
        key = (entry.get("page_id"), entry.get("route_id"))
        assert key not in seen, (
            f"duplicate source-of-truth for page_id={key[0]} route_id={key[1]}"
        )
        seen.add(key)


# ---------------------------------------------------------------------------
# 11. manifest carries completeness information
# ---------------------------------------------------------------------------

def test_manifest_has_completeness_info():
    manifest = _load_manifest()
    has_completeness = (
        "completeness_note" in manifest
        or "complete_capture_required" in manifest
        or any("completeness" in str(k).lower() for k in manifest.keys())
    )
    assert has_completeness, (
        "manifest must carry completeness information "
        "(completeness_note / complete_capture_required)"
    )


# ---------------------------------------------------------------------------
# 12. normal tests do not require external lookup
# ---------------------------------------------------------------------------

def test_manifest_pages_require_no_runtime_network():
    manifest = _load_manifest()
    for entry in manifest.get("pages", []):
        assert entry.get("network_required_at_runtime") is False, (
            f"page {entry.get('page_id')} must not require runtime network "
            f"(network_required_at_runtime must be false)"
        )
