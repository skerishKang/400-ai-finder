"""Unit tests for static-server path-traversal hardening.

These tests exercise :func:`serve_static` and :func:`is_static_request` with a
dummy handler and a temporary ``STATIC_ROOT``. No real HTTP server is started
and no network/subprocess/threading is used.
"""

from __future__ import annotations

import os

import pytest

from src.web import static_server
from src.web.static_server import is_static_request, serve_static


class _RecordingWFile:
    def __init__(self) -> None:
        self.data = b""

    def write(self, data: bytes) -> int:
        self.data += data
        return len(data)


class DummyHandler:
    def __init__(self, path: str) -> None:
        self.path = path
        self.status: int | None = None
        self.error: int | None = None
        self.headers: dict[str, str] = {}
        self.wfile = _RecordingWFile()

    def send_response(self, status: int, *args, **kwargs) -> None:
        self.status = status

    def send_error(self, code: int, *args, **kwargs) -> None:
        self.error = code
        self.status = code

    def send_header(self, name: str, value: str) -> None:
        self.headers[name] = value

    def end_headers(self) -> None:
        pass


@pytest.fixture()
def static_root(tmp_path, monkeypatch):
    root = tmp_path / "static"
    root.mkdir()
    (root / "app.js").write_text("console.log('hi');", encoding="utf-8")
    css = root / "css"
    css.mkdir()
    (css / "style.css").write_text("body{}", encoding="utf-8")
    # A sibling directory with a prefix-collision name, plus an outside file.
    evil = tmp_path / "static-evil"
    evil.mkdir()
    (evil / "secret.txt").write_text("EVIL", encoding="utf-8")
    (tmp_path / "outside_secret.txt").write_text("OUTSIDE", encoding="utf-8")
    monkeypatch.setattr(static_server, "STATIC_ROOT", str(root))
    return root


def _serve(path: str) -> DummyHandler:
    handler = DummyHandler(path)
    serve_static(handler)
    return handler


def _assert_404(handler: DummyHandler) -> None:
    assert handler.error == 404
    assert handler.wfile.data == b""


def _assert_200(handler: DummyHandler, expected_body: bytes) -> None:
    assert handler.error is None
    assert handler.status == 200
    assert handler.wfile.data == expected_body


def test_normal_file_served_with_content_type_and_body(static_root) -> None:
    handler = _serve("/static/app.js")
    _assert_200(handler, b"console.log('hi');")
    assert handler.headers["Content-Type"] == "text/javascript"
    assert handler.headers["Content-Length"] == str(len(b"console.log('hi');"))


def test_missing_file_returns_404(static_root) -> None:
    _assert_404(_serve("/static/nope.js"))


def test_subdirectory_file_under_static_root_served_200(static_root) -> None:
    handler = _serve("/static/css/style.css")
    _assert_200(handler, b"body{}")
    assert handler.headers["Content-Type"] == "text/css"


def test_dotdot_escape_attempt_returns_404(static_root) -> None:
    _assert_404(_serve("/static/../outside_secret.txt"))


def test_deep_dotdot_escape_attempt_returns_404(static_root) -> None:
    _assert_404(_serve("/static/../../outside_secret.txt"))


def test_prefix_collision_sibling_directory_is_blocked(static_root) -> None:
    # Regression for the old ``startswith`` prefix bug: ``/srv/static`` must
    # not match ``/srv/static-evil``.
    _assert_404(_serve("/static/../static-evil/secret.txt"))


@pytest.mark.parametrize(
    "encoded_path",
    [
        "/static/%2e%2e/%2e%2e/etc/passwd",
        "/static/%2e%2e/outside_secret.txt",
        "/static/%2E%2E/%2E%2E/etc/passwd",
    ],
)
def test_encoded_traversal_bypass_returns_404(static_root, encoded_path: str) -> None:
    _assert_404(_serve(encoded_path))


@pytest.mark.parametrize(
    "abs_path",
    [
        "/static//etc/passwd",
        "/static///etc/passwd",
        "/static/C:\\windows\\system32\\drivers\\etc\\hosts",
    ],
)
def test_absolute_path_injection_returns_404(static_root, abs_path: str) -> None:
    _assert_404(_serve(abs_path))


@pytest.mark.parametrize(
    "mixed_path",
    [
        "/static/..\\..\\etc\\passwd",
        "/static/css/..\\..\\..\\outside_secret.txt",
        "/static/..%5c..%5cetc%5cpasswd",
    ],
)
def test_backslash_slash_mixing_returns_404(static_root, mixed_path: str) -> None:
    _assert_404(_serve(mixed_path))


def test_empty_static_path_returns_404(static_root) -> None:
    _assert_404(_serve("/static/"))


def test_symlink_pointing_outside_base_is_blocked(static_root, tmp_path) -> None:
    link = static_root / "evil_link"
    target = tmp_path / "outside_secret.txt"
    try:
        os.symlink(target, link)
    except OSError as exc:  # pragma: no cover - unsupported filesystems
        pytest.skip(f"symlink unsupported: {exc}")
    _assert_404(_serve("/static/evil_link"))


def test_symlink_pointing_inside_base_is_allowed(static_root) -> None:
    target = static_root / "app.js"
    link = static_root / "alias.js"
    try:
        os.symlink(target, link)
    except OSError as exc:  # pragma: no cover - unsupported filesystems
        pytest.skip(f"symlink unsupported: {exc}")
    handler = _serve("/static/alias.js")
    _assert_200(handler, b"console.log('hi');")


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/static/app.js", True),
        ("/static/css/style.css", True),
        ("/static/", True),
        ("/static/../x", False),
        ("/static/..%2f", False),
        ("/static", False),
        ("/api/static/x", False),
        ("/STATIC/app.js", False),
    ],
)
def test_is_static_request(path: str, expected: bool) -> None:
    assert is_static_request(path) is expected


def test_no_forbidden_imports() -> None:
    import ast

    module_path = os.path.join("src", "web", "static_server.py")
    tree = ast.parse(open(module_path, encoding="utf-8").read())
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                used.add(alias.name)
                used.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            used.add(node.module)
            used.add(node.module.split(".", 1)[0])
    forbidden = {
        "requests",
        "httpx",
        "urllib",
        "subprocess",
        "threading",
        "asyncio",
        "concurrent",
        "socket",
        "ssl",
        "http",
        "firecrawl",
        "playwright",
    }
    assert used.isdisjoint(forbidden), f"forbidden imports: {used & forbidden}"
