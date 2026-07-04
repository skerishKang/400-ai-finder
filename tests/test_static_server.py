"""Tests for the static file server security boundary."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from io import BytesIO
from pathlib import Path

from src.web.static_server import STATIC_ROOT, serve_static


class DummyHandler(BaseHTTPRequestHandler):
    def __init__(self, path: str):
        self.path = path
        self.status: int | None = None
        self.headers_sent: list[tuple[str, str]] = []
        self.body = BytesIO()
        self.wfile = self.body

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, key: str, value: str) -> None:
        self.headers_sent.append((key, value))

    def end_headers(self) -> None:
        pass

    def send_error(self, status: int) -> None:
        self.status = status


def test_serve_static_rejects_commonpath_traversal():
    """Path traversal using repeated parent segments must be rejected."""
    handler = DummyHandler("/static/mobile/../../../secret.txt")
    serve_static(handler)
    assert handler.status == 404


def test_serve_static_allows_existing_static_file(tmp_path):
    """Existing static files under STATIC_ROOT are served normally."""
    css_path = Path(STATIC_ROOT) / "mobile" / "mobile_base.css"
    handler = DummyHandler("/static/mobile/mobile_base.css")
    serve_static(handler)
    assert handler.status == 200
    assert css_path.read_text(encoding="utf-8") in handler.body.getvalue().decode("utf-8")
