"""Static contract for the #919 first-use chat shell and the #1065 shared token layer.

This file is executed by `.github/workflows/mvp-contracts.yml`, so the #1065
shared-visual-token source-contract lives here (not in a standalone file).
"""

from html.parser import HTMLParser
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


# ── #1066 prioritized resident tasks on first use ──────────────────────────

PRIMARY_CANONICAL = [
    "불법 주정차 신고는 어디서 하나요?",
    "공동주택 관련 문의는 어느 부서에 해야 하나요?",
    "매트리스 폐기 신청은 어디서 하나요?",
]
SECONDARY_CANONICAL = [
    "여권 발급은 어디서 하나요?",
    "무인민원발급기 어디 있어요?",
    "가로등이 고장났어요. 신고할게요",
    "쓰레기 무단투기 신고할래 (AI 도움)",
]
ALL_CANONICAL = PRIMARY_CANONICAL + SECONDARY_CANONICAL

FORBIDDEN_FIRST_SCREEN = [
    "demo",
    "시연",
    "poc",
    "연결 안 됨",
    "연결되지 않음",
    "테스트용",
    "개발자용",
]
# Civic canvas content markers — the entry panel must not clone/rephrase them.
CIVIC_CLONE_MARKERS = [
    "BUKGU AI CIVIC BROWSER",
    "북구의 모든 행정",
    "home-identity.png",
    "bg-home-",
]


class _EntryPanelParser(HTMLParser):
    """Extracts the entry-panel fragment and separates primary/secondary tasks.

    Uses a section-id stack so the primary and secondary groups are identified
    by their DOM scope rather than a naive substring count.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._section_stack = []
        self._capture = False
        self._fragment = []
        self.primary_questions = []
        self.secondary_questions = []
        self.all_questions = []
        self.task_types = []
        self.toggle_expanded = None
        self.toggle_controls = None
        self.secondary_hidden = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        gid = d.get("id")
        if gid == "chat-entry-panel":
            self._capture = True
        if self._capture:
            self._fragment.append(self.get_starttag_text())
        if self._capture and tag == "section" and gid in (
            "chat-primary-tasks",
            "chat-secondary-tasks",
        ):
            self._section_stack.append(gid)
        if self._capture and tag == "button" and "data-chip-question" in d:
            q = d.get("data-chip-question")
            self.all_questions.append(q)
            if "chat-primary-tasks" in self._section_stack:
                self.primary_questions.append(q)
            elif "chat-secondary-tasks" in self._section_stack:
                self.secondary_questions.append(q)
            self.task_types.append(d.get("type"))
        if self._capture and gid == "chat-more-tasks":
            self.toggle_expanded = d.get("aria-expanded")
            self.toggle_controls = d.get("aria-controls")
        if self._capture and gid == "chat-secondary-tasks":
            self.secondary_hidden = "hidden" in d

    def handle_endtag(self, tag):
        if self._capture:
            self._fragment.append("</" + tag + ">")
        if tag == "section" and self._section_stack:
            self._section_stack.pop()
        if tag == "section" and "id=\"chat-entry-panel\"" in "".join(self._fragment):
            # conservative: rely on stack depth instead
            pass

    def fragment(self):
        return "".join(self._fragment)


def _parse_entry_panel():
    p = _EntryPanelParser()
    p.feed(HTML)
    return p


def _extract_entry_fragment():
    start = HTML.index('id="chat-entry-panel"')
    open_pos = HTML.rfind("<section", 0, start)
    depth = 0
    import re

    for m in re.finditer(r"<(/?)(section)\b[^>]*>", HTML[open_pos:]):
        depth += 1 if m.group(1) != "/" else -1
        if depth == 0:
            return HTML[open_pos : open_pos + m.end()]
    return HTML[open_pos:]


def test_entry_panel_exists():
    assert 'id="chat-entry-panel"' in HTML


def test_entry_panel_has_single_concise_service_intro():
    frag = _extract_entry_fragment()
    # Exactly one intro block and one entry title.
    assert frag.count('class="chat-entry__intro"') == 1
    assert frag.count('id="chat-entry-title"') == 1
    # Intro is concise (a heading + one short paragraph, not a long essay).
    intro = frag[frag.index('chat-entry__intro') :]
    intro = intro[: intro.index("</div>")]
    assert len(intro) < 400
    # The entry intro must not duplicate the old greeting bubble wording.
    assert "안녕하세요. 북구청 민원 안내 AI입니다" not in frag


def test_entry_primary_group_exists():
    assert 'id="chat-primary-tasks"' in HTML


def test_entry_primary_task_count_is_three():
    p = _parse_entry_panel()
    assert len(p.primary_questions) == 3


def test_entry_secondary_group_exists():
    assert 'id="chat-secondary-tasks"' in HTML


def test_entry_secondary_task_count_is_four():
    p = _parse_entry_panel()
    assert len(p.secondary_questions) == 4


def test_entry_secondary_initially_hidden():
    p = _parse_entry_panel()
    assert p.secondary_hidden is True


def test_entry_toggle_has_expanded_false():
    p = _parse_entry_panel()
    assert p.toggle_expanded == "false"


def test_entry_toggle_controls_secondary():
    p = _parse_entry_panel()
    assert p.toggle_controls == "chat-secondary-tasks"


def test_entry_all_seven_canonical_questions_exact():
    p = _parse_entry_panel()
    assert set(p.all_questions) == set(ALL_CANONICAL)
    for q in ALL_CANONICAL:
        assert q in p.all_questions


def test_entry_canonical_questions_unique():
    p = _parse_entry_panel()
    assert len(p.all_questions) == len(set(p.all_questions))


def test_entry_task_buttons_are_type_button():
    p = _parse_entry_panel()
    assert len(p.task_types) == 7
    assert all(t == "button" for t in p.task_types)


def test_entry_composer_outside_task_scroll_region():
    # Composer is defined after the entry panel content in the DOM, so it lives
    # outside the scrollable task region (and inside the chat shell).
    assert HTML.index("id=\"chat-composer-form\"") > HTML.index("id=\"chat-secondary-tasks\"")
    shell = _visible_chat_shell()
    assert 'id="chat-composer-form"' in shell
    assert 'id="chat-entry-panel"' in shell


def test_entry_visible_panel_has_no_forbidden_framing():
    frag = _extract_entry_fragment().lower()
    for forbidden in FORBIDDEN_FIRST_SCREEN:
        assert forbidden not in frag, f"forbidden first-screen framing: {forbidden}"


def test_entry_panel_does_not_clone_civic_content():
    frag = _extract_entry_fragment()
    for marker in CIVIC_CLONE_MARKERS:
        assert marker not in frag, f"entry panel clones civic content: {marker}"


def test_entry_shared_token_stylesheet_still_linked():
    assert "citizen-shared-tokens.css" in HTML
