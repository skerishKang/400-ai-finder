"""Static contract for the #919 first-use chat shell and the #1065 shared token layer.

This file is executed by `.github/workflows/mvp-contracts.yml`, so the #1065
shared-visual-token source-contract lives here (not in a standalone file).
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
HTML = (STATIC / "citizen-action-demo.html").read_text(encoding="utf-8")
TOKENS = (STATIC / "citizen-shared-tokens.css").read_text(encoding="utf-8")
COPILOT = (STATIC / "citizen-copilot-shell.css").read_text(encoding="utf-8")
CANVAS = (STATIC / "citizen-action-demo-canvas.css").read_text(encoding="utf-8")
DOCS = (ROOT / "docs" / "design" / "shared-visual-tokens.md").read_text(encoding="utf-8")


# ── Canonical inventory (source of truth for the contract) ──────────────────
SHARED_TOKENS = {
    "--mvp-radius-sm",
    "--mvp-transition-fast",
}

ASSISTANT_TOKENS = {
    # neutral text + divider palette
    "--mvp-color-text",
    "--mvp-color-text-muted",
    "--mvp-color-surface",
    "--mvp-color-surface-subtle",
    "--mvp-color-surface-2",
    "--mvp-color-divider",
    "--mvp-color-border-soft",
    "--mvp-color-border-accent",
    # status colors
    "--mvp-color-success",
    "--mvp-color-error",
    "--mvp-color-busy",
    "--mvp-color-focus",
    "--mvp-color-accent",
    # keyboard focus-ring geometry (assistant-only, not shared)
    "--mvp-focus-ring-width",
    "--mvp-focus-ring-offset",
    # typography scale + weight
    "--mvp-font-size-xs",
    "--mvp-font-size-sm",
    "--mvp-font-size-base",
    "--mvp-font-size-md",
    "--mvp-font-size-lg",
    "--mvp-font-size-input",
    "--mvp-font-size-send",
    "--mvp-font-size-xl",
    "--mvp-font-size-2xl",
    "--mvp-weight-semibold",
    "--mvp-weight-bold",
    # radii actually used by the assistant
    "--mvp-radius-xs",
    "--mvp-radius-md",
    # base transition duration
    "--mvp-transition-base",
}

ALL_TOKENS = SHARED_TOKENS | ASSISTANT_TOKENS

# Speculative tokens removed (never connected to any production selector).
SPECULATIVE_REMOVED = {
    "--mvp-radius-lg",
    "--mvp-radius-pill",
    "--mvp-transition-slow",
    "--mvp-control-min-height",
    "--mvp-touch-target",
    "--mvp-color-warning",
    "--mvp-color-disabled-fg",
    "--mvp-color-disabled-bg",
    "--mvp-space-1",
    "--mvp-space-2",
    "--mvp-space-3",
    "--mvp-space-4",
    "--mvp-space-5",
    "--mvp-space-6",
    "--mvp-weight-regular",
    "--mvp-weight-medium",
    "--mvp-weight-extrabold",
}


def _strip_comments(text: str) -> str:
    return __import__("re").sub(r"/\*[\s\S]*?\*/", "", text)


def _token_names_defined(text: str) -> set:
    return set(__import__("re").findall(r"(?:^|\s)(--[a-z0-9-]+)\s*:", text))


def _used_vars(text: str) -> set:
    return set(__import__("re").findall(r"var\((--[a-z0-9-]+)\)", text))


def _source_inventory(tokens_text: str):
    """Parse the [shared] / [assistant] ownership banners in the token file."""
    root = tokens_text.split("@media (prefers-reduced-motion", 1)[0]
    owner = None
    shared, assistant = set(), set()
    for line in root.splitlines():
        stripped = line.strip()
        if stripped.startswith("[shared]"):
            owner = "shared"
        elif stripped.startswith("[assistant]"):
            owner = "assistant"
        m = __import__("re").match(r"(--[a-z0-9-]+)\s*:", stripped)
        if m and owner and not m.group(1).startswith("--civic-"):
            (shared if owner == "shared" else assistant).add(m.group(1))
    return shared, assistant


def _docs_tokens_between(md: str, start: str, end: str) -> set:
    i = md.index(start)
    j = md.index(end, i)
    return set(__import__("re").findall(r"`(--mvp-[a-z0-9-]+)`", md[i:j]))


def _visible_chat_shell() -> str:
    start = HTML.index('<aside class="chat-shell"')
    end = HTML.index("</aside>", start)
    return HTML[start:end]


# ── #919 first-use chat shell contract ──────────────────────────────────────


def test_fresh_document_declares_entry_state_and_inert_clone():
    assert '<body data-first-use-state="entry">' in HTML
    assert 'id="demo-canvas"' in HTML
    assert 'aria-hidden="true" inert' in HTML
    assert 'citizen-first-use-shell.css' in HTML
    assert 'citizen-first-use-shell.js' in HTML


def test_entry_chat_has_enabled_form_and_reset_control():
    shell = _visible_chat_shell()
    assert 'id="chat-composer-form"' in shell
    assert 'id="chat-composer-input"' in shell
    assert 'id="chat-composer-send"' in shell
    assert 'id="chat-reset"' in shell
    assert 'disabled' not in shell


def test_entry_chat_does_not_embed_legacy_progress_widget():
    shell = _visible_chat_shell()
    assert 'chat-progress' not in shell


# ── #1065 shared token contract ─────────────────────────────────────────────

# ── Load order ──


def test_token_stylesheet_is_loaded_before_assistant_css():
    assert "citizen-shared-tokens.css" in HTML
    assert "citizen-copilot-shell.css" in HTML
    assert HTML.index("citizen-shared-tokens.css") < HTML.index(
        "citizen-copilot-shell.css"
    )


# ── Exact defined set + ownership ──


def test_defined_token_set_is_exact():
    defined = _token_names_defined(_strip_comments(TOKENS))
    assert defined == ALL_TOKENS


def test_source_token_ownership_matches_contract():
    shared, assistant = _source_inventory(TOKENS)
    assert shared == SHARED_TOKENS
    assert assistant == ASSISTANT_TOKENS
    assert shared.isdisjoint(assistant)


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
    for removed in SPECULATIVE_REMOVED:
        assert removed not in TOKENS, f"speculative token should be removed: {removed}"


# ── No unresolved / unused variables in assistant CSS ──


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


def test_every_defined_token_is_consumed_by_assistant_css():
    copilot = _strip_comments(COPILOT)
    used = _used_vars(copilot)
    defined = _token_names_defined(_strip_comments(TOKENS))
    for name in defined:
        assert name in used, f"defined token not consumed by assistant CSS: {name}"


def test_only_allowed_layout_variable_is_copilot_rail_width():
    copilot_defined = _token_names_defined(COPILOT)
    copilot_vars = {n for n in copilot_defined if n.startswith("--copilot-")}
    assert copilot_vars == {"--copilot-rail-width"}
    assert "--copilot-rail-width: 280px;" in COPILOT


def test_assistant_css_uses_only_defined_tokens():
    used = _used_vars(_strip_comments(COPILOT))
    assert used, "assistant CSS should consume at least one shared token"
    assert "--mvp-color-text" in used
    assert "--mvp-color-divider" in used


# ── Shared primitives embodied by the civic canvas (no edit to civic) ──


def test_shared_primitives_are_embodied_by_civic_canvas():
    assert "--mvp-radius-sm: 4px;" in TOKENS
    assert "border-radius: 4px" in CANVAS
    assert "--mvp-transition-fast: 120ms;" in TOKENS
    assert "0.12s" in CANVAS


def test_civic_canvas_is_not_tokenized():
    """Civic canvas must keep its own exact-clone literals (not reference tokens)."""
    assert "var(--mvp-" not in CANVAS
    assert "var(--mvp-color-text)" not in CANVAS


# ── Interaction / state contracts ──


def test_focus_visible_present_in_assistant_css():
    assert ":focus-visible" in COPILOT


def test_status_and_disabled_states_present():
    copilot = _strip_comments(COPILOT)
    used = _used_vars(copilot)
    assert "--mvp-color-success" in TOKENS and "--mvp-color-success" in used
    assert "--mvp-color-error" in TOKENS and "--mvp-color-error" in used
    assert "--mvp-color-busy" in TOKENS and "--mvp-color-busy" in used
    assert ":disabled" in COPILOT


def test_reduced_motion_block_present():
    assert "prefers-reduced-motion: reduce" in TOKENS
    assert "transition-duration: 0.001ms" in TOKENS


# ── Docs / source inventory parity ──


def test_docs_inventory_matches_source():
    shared_docs = _docs_tokens_between(DOCS, "### shared", "### assistant")
    assistant_docs = _docs_tokens_between(DOCS, "### assistant", "## Removed")
    assert shared_docs == SHARED_TOKENS
    assert assistant_docs == ASSISTANT_TOKENS
