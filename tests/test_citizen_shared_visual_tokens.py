"""Committed contract for the #1065 shared visual token layer.

Locks the canonical token layer so future edits cannot silently break:
  * token stylesheet load order (tokens before the assistant CSS)
  * key token values + ownership
  * no unresolved CSS custom properties in the assistant CSS
  * the genuinely-shared primitives are embodied by the civic canvas literals
  * focus-visible, success/error/busy/disabled, and reduced-motion handling
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"

HTML = (STATIC / "citizen-action-demo.html").read_text(encoding="utf-8")
TOKENS = (STATIC / "citizen-shared-tokens.css").read_text(encoding="utf-8")
COPILOT = (STATIC / "citizen-copilot-shell.css").read_text(encoding="utf-8")
CANVAS = (STATIC / "citizen-action-demo-canvas.css").read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    return __import__("re").sub(r"/\*[\s\S]*?\*/", "", text)


def _token_names_defined(text: str) -> set:
    import re

    return set(re.findall(r"(?:^|\s)(--[a-z0-9-]+)\s*:", text))


def _used_vars(text: str) -> set:
    import re

    return set(re.findall(r"var\((--[a-z0-9-]+)\)", text))


# ── Load order ──────────────────────────────────────────────────────


def test_token_stylesheet_is_loaded_before_assistant_css():
    assert "citizen-shared-tokens.css" in HTML
    assert "citizen-copilot-shell.css" in HTML
    assert HTML.index("citizen-shared-tokens.css") < HTML.index(
        "citizen-copilot-shell.css"
    )


# ── Key token values + ownership ───────────────────────────────────


def test_shared_primitive_values():
    assert "--mvp-radius-sm: 4px;" in TOKENS
    assert "--mvp-transition-fast: 120ms;" in TOKENS
    assert "--mvp-focus-ring-width: 2px;" in TOKENS
    assert "--mvp-focus-ring-offset: 2px;" in TOKENS


def test_assistant_token_values():
    for expected in (
        "--mvp-color-text: #0d0d0f;",
        "--mvp-color-surface: #ffffff;",
        "--mvp-color-divider: #e6e6ea;",
        "--mvp-color-success: #27ae60;",
        "--mvp-color-error: #c0392b;",
        "--mvp-color-busy: #2980b9;",
        "--mvp-color-accent: #ef6a4c;",
        "--mvp-font-size-md: 0.875rem;",
        "--mvp-font-size-2xl: 1.375rem;",
        "--mvp-transition-base: 150ms;",
    ):
        assert expected in TOKENS, f"missing token definition: {expected}"


def test_speculative_tokens_removed():
    """Tokens that were not connected to any production selector were removed."""
    for removed in (
        "--mvp-radius-lg",
        "--mvp-radius-pill",
        "--mvp-transition-slow",
        "--mvp-control-min-height",
        "--mvp-touch-target",
        "--mvp-color-warning",
        "--mvp-color-disabled-fg",
        "--mvp-color-disabled-bg",
        "--mvp-space-1",
        "--mvp-weight-regular",
        "--mvp-weight-extrabold",
    ):
        assert removed not in TOKENS, f"speculative token should be removed: {removed}"


# ── No unresolved custom properties in assistant CSS ────────────────


def test_assistant_css_has_no_unresolved_variables():
    copilot = _strip_comments(COPILOT)
    defined = _token_names_defined(TOKENS)
    used = _used_vars(copilot)
    # The only allowed --copilot-* reference is the layout-only rail width.
    for name in used:
        if name.startswith("--copilot-"):
            assert name == "--copilot-rail-width", (
                f"unexpected --copilot-* reference in assistant CSS: {name}"
            )
            continue
        assert name in defined, f"assistant CSS references undefined token: {name}"


def test_assistant_css_uses_only_defined_tokens():
    used = _used_vars(_strip_comments(COPILOT))
    assert used, "assistant CSS should consume at least one shared token"
    assert "--mvp-color-text" in used
    assert "--mvp-color-divider" in used


# ── Shared primitives embodied by the civic canvas (no edit to civic) ──


def test_shared_primitives_are_embodied_by_civic_canvas():
    # radius-sm (4px) and transition-fast (120ms == 0.12s) must appear as
    # hard-coded literals in the exact-clone civic canvas.
    assert "--mvp-radius-sm: 4px;" in TOKENS
    assert "border-radius: 4px" in CANVAS
    assert "--mvp-transition-fast: 120ms;" in TOKENS
    assert "0.12s" in CANVAS


def test_civic_canvas_is_not_tokenized():
    """Civic canvas must keep its own exact-clone literals (not reference tokens)."""
    assert "var(--mvp-" not in CANVAS
    assert "var(--mvp-color-text)" not in CANVAS


# ── Interaction / state contracts ───────────────────────────────────


def test_focus_visible_present_in_assistant_css():
    assert ":focus-visible" in COPILOT


def test_status_and_disabled_states_present():
    # success / error / busy are defined as tokens and consumed.
    assert "--mvp-color-success" in TOKENS and "--mvp-color-success" in _used_vars(
        _strip_comments(COPILOT)
    )
    assert "--mvp-color-error" in TOKENS and "--mvp-color-error" in _used_vars(
        _strip_comments(COPILOT)
    )
    assert "--mvp-color-busy" in TOKENS and "--mvp-color-busy" in _used_vars(
        _strip_comments(COPILOT)
    )
    # disabled state exists (expressed via opacity + cursor in the assistant).
    assert ":disabled" in COPILOT


def test_reduced_motion_block_present():
    assert "prefers-reduced-motion: reduce" in TOKENS
    assert "transition-duration: 0.001ms" in TOKENS
