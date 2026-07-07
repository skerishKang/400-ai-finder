"""Static contract for the #919 first-use shell."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
HTML = (STATIC / "citizen-action-demo.html").read_text(encoding="utf-8")
JS = (STATIC / "citizen-first-use-shell.js").read_text(encoding="utf-8")
CSS = (STATIC / "citizen-first-use-shell.css").read_text(encoding="utf-8")


def test_first_use_shell_is_loaded_after_existing_local_demo_scripts():
    assert HTML.index("citizen-action-demo-canvas.js") < HTML.index("citizen-first-use-shell.js")
    assert HTML.index("citizen-action-executor.js") < HTML.index("citizen-first-use-shell.js")
    assert 'data-first-use-state="entry"' in HTML


def test_first_use_shell_defines_entry_transition_split_and_reset_contract():
    assert 'STATE_ENTRY = "entry"' in JS
    assert 'STATE_TRANSITIONING = "transitioning"' in JS
    assert 'STATE_SPLIT = "split"' in JS
    assert "beginSupportedTransition" in JS
    assert "completeSplit" in JS
    assert "resetToEntry" in JS
    assert "setCanvasAvailability(false)" in JS
    assert "setCanvasAvailability(true)" in JS


def test_first_use_shell_is_local_only_and_fail_closed():
    assert '"불법 주정차 신고는 어디서 하나요?": true' in JS
    assert "isSupportedQuestion(question)" in JS
    assert "지원 범위의 질문으로 다시 입력해 주세요." in JS
    assert "fetch(" not in JS
    assert "localStorage" not in JS
    assert "sessionStorage" not in JS
    assert "document.cookie" not in JS


def test_first_use_shell_has_reduced_motion_and_noninteractive_entry_clone_rules():
    assert "prefers-reduced-motion: reduce" in CSS
    assert "first-use-shell--no-motion" in CSS
    assert "pointer-events: none" in CSS
    assert "aria-hidden" in JS
    assert "inert" in JS
