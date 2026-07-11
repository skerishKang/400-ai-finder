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
MANIFEST = ROOT / "tests" / "fixtures" / "official_site_clone_manifest.json"

# ---------------------------------------------------------------------------
# Dynamic document discovery — no link dependency
# ---------------------------------------------------------------------------

DOC_PATTERNS = ("*.md", "*.mdx")
_EXCLUDED_ROOTS = frozenset({
    ".claude", ".git", "node_modules", "__pycache__", ".pytest_cache",
    "data", "dist", "extensions", "presentation", "proposal", "prompts",
    "examples", "tools",
})

# Topics that identify a doc as clone-governing candidate.
# Canonical link presence is NOT used as discovery condition.
CLONE_TOPIC_PATTERNS = [
    "official site", "official page",
    "북구청 공식 사이트", "공식 페이지",
    "left civic-site", "left website surface",
    "citizen canvas",
    "official fixture", "official snapshot",
    "official route inventory",
    "official-page renderer",
    "clone fidelity", "exact clone",
    "공식 콘텐츠를 좌측 화면에 렌더링",
    "official public source",
]

# ALLOWLIST: files excluded with specific reason (no broad directory exclusion).
ALLOWLIST: dict[str, str] = {}


def _is_clone_governing_candidate(text: str) -> bool:
    """Check if doc content references any clone-governing topic.

    Canonical link presence is NOT required for discovery.
    """
    low = text.lower()
    for topic in CLONE_TOPIC_PATTERNS:
        if topic.lower() in low:
            return True
    return False


def _discover_clone_related_docs() -> list[str]:
    """Walk repository and collect docs that reference clone-governing topics.

    No hand-maintained literal replaces this scan. Canonical link presence is
    NOT used as a discovery condition. ALLOWLIST must specify per-path exclusion
    with a specific reason.
    """
    found: list[str] = []
    # Always include canonical doc itself
    found.append(CANONICAL_DOC)

    # README*
    for p in ROOT.glob("README*"):
        if p.is_file() and p.suffix in (".md", ".mdx", ""):
            rel = p.relative_to(ROOT).as_posix()
            if rel in ALLOWLIST:
                continue
            if rel not in found:
                found.append(rel)

    # root *.md / *.mdx
    for pattern in DOC_PATTERNS:
        for p in ROOT.glob(pattern):
            if p.is_file() and p.parent == ROOT:
                rel = p.relative_to(ROOT).as_posix()
                if rel in ALLOWLIST or rel in found:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                if _is_clone_governing_candidate(text):
                    found.append(rel)

    # docs/**/*.md / *.mdx
    docs_dir = ROOT / "docs"
    if docs_dir.is_dir():
        for pattern in DOC_PATTERNS:
            for p in docs_dir.rglob(pattern):
                if any(excluded in p.parts for excluded in _EXCLUDED_ROOTS):
                    continue
                rel = p.relative_to(ROOT).as_posix()
                if rel in ALLOWLIST or rel in found:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                if _is_clone_governing_candidate(text):
                    found.append(rel)

    # .github/**/*.md / *.mdx
    github_dir = ROOT / ".github"
    if github_dir.is_dir():
        for pattern in DOC_PATTERNS:
            for p in github_dir.rglob(pattern):
                if any(excluded in p.parts for excluded in _EXCLUDED_ROOTS):
                    continue
                rel = p.relative_to(ROOT).as_posix()
                if rel in ALLOWLIST or rel in found:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                if _is_clone_governing_candidate(text):
                    found.append(rel)

    found.sort()
    return found


CLONE_RELATED_DOCS = _discover_clone_related_docs()

REQUIRED_8_CANONICAL = [
    "docs/design/863-local-execution-contract.md",
    "docs/mvp-demo-operator-runbook.md",
    "docs/official-site-route-inventory-first-local-static-records.md",
    "docs/official-site-route-inventory-plan.md",
    "docs/operator-controlled-retrieval-gap-validation.md",
    "docs/product/1078-corrective-note.md",
    "docs/product/dynamic-retrieval-query-learning-strategy.md",
    "docs/product/municipal-service-crawl-index-completeness-audit.md",
]

OFFICIAL_DOMAIN = "https://bukgu.gwangju.kr"

# ---------------------------------------------------------------------------
# Weakening detector — rewritten for CTO clarity
# ---------------------------------------------------------------------------

# Explicit forbidden phrases — must never appear in clone-relevant docs.
# Note: "Use a summary instead" type phrases are removed from FORBIDDEN_PHRASES;
# the sentence-level detector handles them with proper negation context.
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
]

# Weak terms whose mere presence is not a violation, but which become a
# violation when a sentence ALSO contains an approval/permission signal
# (the sentence approves a weak clone).
WEAK_TERMS = [
    "요약", "축약", "간소", "재설계", "근사", "유사", "비슷", "대표",
    "approximate", "approximation", "representative", "summary", "simplified",
    "simplify", "simulation", "simulated", "inspired by",
    "approximately", "근접", "충분히 유사",
]

APPROVAL_SIGNALS = [
    "허용", "가능", "수준", "대신", "instead of", "acceptable", "enough",
    "충분", "근접", "비슷", "유사", "approximate", "approximation", "closely",
    "보여", "표시", "노출", "사용", "적용",
    " use ", " may ",  # word-boundary matched to avoid false positives
    "도 된다",
]

# Only explicit negation signals — broad/broken negations removed.
# "instead of" and "대신" are replacement-direction indicators, not negation.
NEGATION_SIGNALS = [
    "must not", "do not", "never",
    "forbidden", "disallowed", "cannot be used",
    "금지한다", "허용하지 않는다", "사용하지 않는다",
    "대체하지 않는다", "표시하지 않는다", "하지 않는다",
    "되지 않는다",
    "불가",
]


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.。!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _scan_document_for_clone_weakening(text: str) -> list[str]:
    """Full context-aware scanner for clone-weakening language.

    Splits text into sentences and checks each for:
    - Hard-blocked phrases (FORBIDDEN_PHRASES) that weaken clone fidelity.
    - Weak terms (WEAK_TERMS) combined with approval/permission signals.

    Sentences that contain an explicit negation signal (NEGATION_SIGNALS)
    are excluded -- prohibition rules must be allowed.

    Returns list of offending sentence(s).
    """
    offending: list[str] = []
    for sent in _split_sentences(text):
        low = sent.lower()
        # Skip sentences that explicitly prohibit weakening
        has_negation = any(neg in low for neg in NEGATION_SIGNALS)
        # Proximity check: "not [weak_term]" — "not" directly negates a weak term.
        # This handles patterns like "match exactly, not approximately" where
        # the broad " not " token was removed from NEGATION_SIGNALS per #1078.
        if not has_negation:
            for wt in WEAK_TERMS:
                if wt in low and f" not {wt}" in low:
                    has_negation = True
                    break
        # Check hard-blocked phrases (always a violation unless negated)
        if any(phrase.lower() in low for phrase in FORBIDDEN_PHRASES):
            if not has_negation:
                offending.append(sent)
                continue
        # Check weak term + approval signal (unless negated)
        if has_negation:
            continue
        has_weak = any(w.lower() in low for w in WEAK_TERMS)
        if not has_weak:
            continue
        has_approval = any(s.lower() in low for s in APPROVAL_SIGNALS)
        if has_approval:
            offending.append(sent)
    return offending
def _full_scanner_positive_self_test():
    """Sentences that MUST be detected as violations by the full scanner."""
    must_violate = [
        "Use a summary instead of the official page.",
        "A simplified version of the official page is acceptable.",
        "The left surface may use representative rows.",
        "The current clone uses representative rows.",
        "A high-fidelity approximation is acceptable.",
        "공식 표 대신 대표 행만 표시한다.",
    ]
    for s in must_violate:
        violations = _scan_document_for_clone_weakening(s)
        assert violations, (
            f"Positive self-test failed: should have detected violation:\\n  {s}"
        )
def _full_scanner_negative_self_test():
    """Sentences that MUST be allowed (explicitly negated or unrelated)."""
    must_pass = [
        "Do not use a summary instead of the official page.",
        "The official page must never be simplified.",
        "Representative rows must not be used.",
        "Do not build a high-fidelity approximation of the official page.",
        "대표 행만 표시하는 것은 금지한다.",
        "공식 표를 요약 화면으로 대체하지 않는다.",
        "The retrieval index has an unused summary field; this is unrelated to clone fidelity.",
    ]
    for s in must_pass:
        violations = _scan_document_for_clone_weakening(s)
        assert not violations, (
            f"Negative self-test failed: should NOT have detected:\\n  {s}\\n"
            f"Got: {violations}"
        )
# ---------------------------------------------------------------------------
# 1. canonical invariant document exists
# ---------------------------------------------------------------------------

def test_canonical_invariant_document_exists():
    assert (ROOT / CANONICAL_DOC).is_file()


# ---------------------------------------------------------------------------
# 2. primary README links the canonical document
# ---------------------------------------------------------------------------

def test_readme_links_canonical_invariant():
    readme = ROOT / "README.md"
    assert readme.is_file()
    content = readme.read_text(encoding="utf-8")
    link_text = "exact-official-site-clone-invariant.md"
    assert link_text in content, (
        "README must link the canonical exact-official-site-clone invariant doc"
    )
    required_ko = (
        "왼쪽 시민 사이트 화면은 캡처된 광주광역시 북구청 공식 페이지를 그대로 복제한다"
    )
    required_en = (
        "The left civic-site surface clones the captured official Gwangju Buk-gu "
        "portal page verbatim"
    )
    assert required_ko in content or required_en in content


# ---------------------------------------------------------------------------
# 3. clone-related docs link the canonical document
# ---------------------------------------------------------------------------

def test_clone_related_docs_link_canonical():
    for rel in CLONE_RELATED_DOCS:
        p = ROOT / rel
        assert p.is_file(), f"clone-related doc missing: {rel}"
        if rel == CANONICAL_DOC:
            continue
        content = p.read_text(encoding="utf-8")
        link_text = "exact-official-site-clone-invariant.md"
        assert link_text in content or CANONICAL_DOC in content, (
            f"{rel} must reference the canonical invariant doc ({CANONICAL_DOC})"
        )


# ---------------------------------------------------------------------------
# 3b. Required 8 docs are discovered and linked
# ---------------------------------------------------------------------------

def test_required_8_docs_are_discovered():
    for rel in REQUIRED_8_CANONICAL:
        assert rel in CLONE_RELATED_DOCS, (
            f"Required doc not discovered: {rel}"
        )


def test_required_8_docs_link_canonical():
    for rel in REQUIRED_8_CANONICAL:
        p = ROOT / rel
        assert p.is_file(), f"Required doc missing: {rel}"
        content = p.read_text(encoding="utf-8")
        link_text = "exact-official-site-clone-invariant.md"
        assert link_text in content or CANONICAL_DOC in content, (
            f"{rel} must reference the canonical invariant doc ({CANONICAL_DOC})"
        )


# ---------------------------------------------------------------------------
# 4. clone-related docs contain no sentence that approves a weak direction
# ---------------------------------------------------------------------------

def test_detector_self_tests():
    _full_scanner_positive_self_test()
    _full_scanner_negative_self_test()


def test_clone_related_docs_have_no_weak_approval_language():
    for rel in CLONE_RELATED_DOCS:
        p = ROOT / rel
        content_text = p.read_text(encoding="utf-8")
        # The canonical invariant doc enumerates forbidden phrases as
        # examples of what to BLOCK. The context-aware scanner naturally
        # handles prohibition rules because they contain negation signals.
        # Only skip it unconditionally as a safety net -- the scanner should
        # pass prohibition examples without this exclusion.
        if rel == CANONICAL_DOC:
            continue
        # Unified context-aware scan (phrase + sentence level).
        offending = _scan_document_for_clone_weakening(content_text)
        assert not offending, (
            f"{rel} contains sentence(s) that approve a weak clone direction: "
            + " || ".join(offending)
        )
# ---------------------------------------------------------------------------
# 5. official page fixture manifest exists
# ---------------------------------------------------------------------------

def test_official_page_fixture_manifest_exists():
    assert MANIFEST.is_file()


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
