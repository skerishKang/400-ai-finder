"""Static contract for the #919 first-use chat shell."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src" / "web" / "static" / "citizen-action-demo.html").read_text(encoding="utf-8")


def _visible_chat_shell() -> str:
    start = HTML.index('<aside class="chat-shell"')
    end = HTML.index("  </aside>", start)
    return HTML[start:end]


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
