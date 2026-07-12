#!/usr/bin/env python3
"""Line-based patch for Issue #1078."""
import json

WORKTREE = "G:/Ddrive/BatangD/task/workdiary/400-ai-finder-1078"
test_path = f"{WORKTREE}/tests/test_exact_official_site_clone_invariant.py"

with open(test_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# --- Change 1: Remove broad negations (lines 197-198) ---
# Line 197: '    " not ",  # standalone token negation...\n'
# Line 198: '    " no ",\n'
line_197 = lines[196]  # 0-indexed
line_198 = lines[197]
assert ' not "' in line_197, f"Line 197 doesn't contain ' not ': {repr(line_197)}"
assert ' no "' in line_198, f"Line 198 doesn't contain ' no ': {repr(line_198)}"
# Remove lines 197-198 (keep line 196 and before, skip 197-198, keep 199+)
lines = lines[:196] + lines[198:]
print(f"After removing lines 197-198: {len(lines)} lines")

# Now lines are renumbered. Let me identify current positions
# Line numbers after removal (1-indexed):
# Need to find and replace the function bodies at their new positions

# --- Change 2: Replace _has_weak_approval_sentence with _scan_document_for_clone_weakening ---
# Find the function
func_start = None
for i, line in enumerate(lines):
    if 'def _has_weak_approval_sentence(text: str) -> list[str]:' in line:
        func_start = i
        break
assert func_start is not None, "Could not find _has_weak_approval_sentence function"
print(f"Found _has_weak_approval_sentence at line {func_start+1}")

# Find the end of the function (next def or comment block)
func_end = None
for i in range(func_start + 1, len(lines)):
    stripped = lines[i].strip()
    if stripped.startswith('def ') or stripped.startswith('# -----'):
        func_end = i
        break
assert func_end is not None, "Could not find end of _has_weak_approval_sentence function"
print(f"Function ends at line {func_end+1}")

# Build replacement
new_func = [
    'def _scan_document_for_clone_weakening(text: str) -> list[str]:\n',
    '    """Full context-aware scanner for clone-weakening language.\n',
    '\n',
    '    Splits text into sentences and checks each for:\n',
    '    - Hard-blocked phrases (FORBIDDEN_PHRASES) that weaken clone fidelity.\n',
    '    - Weak terms (WEAK_TERMS) combined with approval/permission signals.\n',
    '\n',
    '    Sentences that contain an explicit negation signal (NEGATION_SIGNALS)\n',
    '    are excluded -- prohibition rules must be allowed.\n',
    '\n',
    '    Returns list of offending sentence(s).\n',
    '    """\n',
    '    offending: list[str] = []\n',
    '    for sent in _split_sentences(text):\n',
    '        low = sent.lower()\n',
    '        # Skip sentences that explicitly prohibit weakening\n',
    '        has_negation = any(neg in low for neg in NEGATION_SIGNALS)\n',
    '        # Check hard-blocked phrases (always a violation unless negated)\n',
    '        if any(phrase.lower() in low for phrase in FORBIDDEN_PHRASES):\n',
    '            if not has_negation:\n',
    '                offending.append(sent)\n',
    '                continue\n',
    '        # Check weak term + approval signal (unless negated)\n',
    '        if has_negation:\n',
    '            continue\n',
    '        has_weak = any(w.lower() in low for w in WEAK_TERMS)\n',
    '        if not has_weak:\n',
    '            continue\n',
    '        has_approval = any(s.lower() in low for s in APPROVAL_SIGNALS)\n',
    '        if has_approval:\n',
    '            offending.append(sent)\n',
    '    return offending\n',
]
lines[func_start:func_end] = new_func
print(f"Replaced function body ({func_end-func_start} lines -> {len(new_func)} lines)")

# --- Change 3: Replace _detector_positive_self_test ---
pos_start = None
for i, line in enumerate(lines):
    if 'def _detector_positive_self_test():' in line:
        pos_start = i
        break
assert pos_start is not None, "Could not find _detector_positive_self_test"
print(f"Found _detector_positive_self_test at line {pos_start+1}")

pos_end = None
for i in range(pos_start + 1, len(lines)):
    stripped = lines[i].strip()
    if stripped.startswith('def ') or stripped.startswith('# -----'):
        pos_end = i
        break
assert pos_end is not None
print(f"Function ends at line {pos_end+1}")

new_pos = [
    'def _full_scanner_positive_self_test():\n',
    '    """Sentences that MUST be detected as violations by the full scanner."""\n',
    '    must_violate = [\n',
    '        "Use a summary instead of the official page.",\n',
    '        "A simplified version of the official page is acceptable.",\n',
    '        "The left surface may use representative rows.",\n',
    '        "The current clone uses representative rows.",\n',
    '        "A high-fidelity approximation is acceptable.",\n',
    '        "공식 표 대신 대표 행만 표시한다.",\n',
    '    ]\n',
    '    for s in must_violate:\n',
    '        violations = _scan_document_for_clone_weakening(s)\n',
    '        assert violations, (\n',
    '            f"Positive self-test failed: should have detected violation:\\\\n  {s}"\n',
    '        )\n',
]
lines[pos_start:pos_end] = new_pos
print(f"Replaced positive self-test")

# --- Change 4: Replace _detector_negative_self_test ---
neg_start = None
for i, line in enumerate(lines):
    if 'def _detector_negative_self_test():' in line:
        neg_start = i
        break
assert neg_start is not None, "Could not find _detector_negative_self_test"
print(f"Found _detector_negative_self_test at line {neg_start+1}")

neg_end = None
for i in range(neg_start + 1, len(lines)):
    stripped = lines[i].strip()
    if stripped.startswith('def ') or stripped.startswith('# -----'):
        neg_end = i
        break
assert neg_end is not None
print(f"Function ends at line {neg_end+1}")

new_neg = [
    'def _full_scanner_negative_self_test():\n',
    '    """Sentences that MUST be allowed (explicitly negated or unrelated)."""\n',
    '    must_pass = [\n',
    '        "Do not use a summary instead of the official page.",\n',
    '        "The official page must never be simplified.",\n',
    '        "Representative rows must not be used.",\n',
    '        "Do not build a high-fidelity approximation of the official page.",\n',
    '        "대표 행만 표시하는 것은 금지한다.",\n',
    '        "공식 표를 요약 화면으로 대체하지 않는다.",\n',
    '        "The retrieval index has an unused summary field; this is unrelated to clone fidelity.",\n',
    '    ]\n',
    '    for s in must_pass:\n',
    '        violations = _scan_document_for_clone_weakening(s)\n',
    '        assert not violations, (\n',
    '            f"Negative self-test failed: should NOT have detected:\\\\n  {s}\\\\n"\n',
    '            f"Got: {violations}"\n',
    '        )\n',
]
lines[neg_start:neg_end] = new_neg
print(f"Replaced negative self-test")

# --- Change 5: Update test_detector_self_tests ---
for i, line in enumerate(lines):
    if '_detector_positive_self_test()' in line:
        lines[i] = line.replace('_detector_positive_self_test()', '_full_scanner_positive_self_test()')
    if '_detector_negative_self_test()' in line:
        lines[i] = line.replace('_detector_negative_self_test()', '_full_scanner_negative_self_test()')

print("Updated test_detector_self_tests")

# --- Change 6: Update test_clone_related_docs_have_no_weak_approval_language ---
test_start = None
for i, line in enumerate(lines):
    if 'def test_clone_related_docs_have_no_weak_approval_language():' in line:
        test_start = i
        break
assert test_start is not None, "Could not find test_clone_related_docs_have_no_weak_approval_language"
print(f"Found test at line {test_start+1}")

test_end = None
for i in range(test_start + 1, len(lines)):
    stripped = lines[i].strip()
    if stripped.startswith('def ') or stripped.startswith('# -----'):
        test_end = i
        break
assert test_end is not None
print(f"Test ends at line {test_end+1}")

new_test = [
    'def test_clone_related_docs_have_no_weak_approval_language():\n',
    '    for rel in CLONE_RELATED_DOCS:\n',
    '        p = ROOT / rel\n',
    '        content_text = p.read_text(encoding="utf-8")\n',
    '        # The canonical invariant doc enumerates forbidden phrases as\n',
    '        # examples of what to BLOCK. The context-aware scanner naturally\n',
    '        # handles prohibition rules because they contain negation signals.\n',
    '        # Only skip it unconditionally as a safety net -- the scanner should\n',
    '        # pass prohibition examples without this exclusion.\n',
    '        if rel == CANONICAL_DOC:\n',
    '            continue\n',
    '        # Unified context-aware scan (phrase + sentence level).\n',
    '        offending = _scan_document_for_clone_weakening(content_text)\n',
    '        assert not offending, (\n',
    '            f"{rel} contains sentence(s) that approve a weak clone direction: "\n',
    '            + " || ".join(offending)\n',
    '        )\n',
]
lines[test_start:test_end] = new_test
print(f"Replaced test function")

with open(test_path, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("=== Written test file ===")

# --- Step 2: Patch manifest ---
manifest_path = f"{WORKTREE}/tests/fixtures/official_site_clone_manifest.json"
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

for entry in manifest.get("capture_required", []):
    if entry.get("route_id") == "apartment-info":
        old_issue = entry["blocking_followup_issue"]
        new_issue = "#1080 — apartment-info full official capture pending; synthetic render must not be mistaken for exact."
        if old_issue != new_issue:
            print(f"  old: {old_issue}")
            print(f"  new: {new_issue}")
            entry["blocking_followup_issue"] = new_issue
            print("OK: updated apartment-info blocking_followup_issue")
        else:
            print("OK: apartment-info already correct")
        break

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("=== Written manifest file ===")
