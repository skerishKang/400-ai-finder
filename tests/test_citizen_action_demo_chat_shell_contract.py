"""Static contract for the visible initial split-chat shell."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src" / "web" / "static" / "citizen-action-demo.html").read_text(
    encoding="utf-8"
)


def _visible_chat_shell() -> str:
    start = HTML.index('<aside class="chat-shell"')
    end = HTML.index("  </aside>", start)
    return HTML[start:end]


def test_initial_chat_shell_has_exact_approved_turns_and_composer():
    shell = _visible_chat_shell()
    expected_turns = [
        "불법 주정차 신고는 어디서 하나요?",
        "북구청 홈페이지에서 신고 경로를 확인하겠습니다.",
        "종합민원 메뉴에서 온라인 민원신청 경로를 찾고 있습니다.",
    ]
    offsets = [shell.index(turn) for turn in expected_turns]
    assert offsets == sorted(offsets)
    assert 'class="chat-shell"' in shell
    assert 'class="chat-thread"' in shell
    assert 'class="chat-composer__send"' in shell
    assert 'aria-label="보내기"' in shell
    assert "보내기" in shell


def test_initial_chat_shell_excludes_unapproved_waiting_copy():
    assert "잠시만 기다려 주세요." not in _visible_chat_shell()
