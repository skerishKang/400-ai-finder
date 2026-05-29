"""Mobile chat UI demo for AI Homepage Finder.

Serves a ChatGPT-style UI at http://localhost:8080 with a
POST /api/ask endpoint backed by SiteDemoRunner.

Usage::

    from src.web.mobile_demo import create_app
    app = create_app(site_id="bukgu_gwangju", snapshot="/tmp/snap.json")
    app.serve_forever()
"""

from __future__ import annotations

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any
from urllib.parse import urlparse

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(_THIS_DIR, "templates", "mobile_demo.html")


def _load_template(site_name: str) -> str:
    """Load the mobile HTML template and replace placeholders."""
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        return f"""<!DOCTYPE html><html lang="ko"><body>
<h1>Template not found</h1><p>{TEMPLATE_PATH}</p></body></html>"""
    return html.replace("{{site_name}}", site_name)


class MobileDemoHandler(BaseHTTPRequestHandler):
    """HTTP handler for the mobile chat demo."""

    site_id: str = "bukgu_gwangju"
    provider: str = "mock"
    snapshot_path: str | None = None
    _runner: Any = None
    _site_name: str = ""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/static/"):
            from .static_server import is_static_request, serve_static

            if is_static_request(self.path):
                serve_static(self)
                return
        parsed = urlparse(self.path)
        if parsed.path in ("/", ""):
            self._serve_html()
        elif parsed.path == "/health":
            self._json_response({"ok": True, "site_id": self.site_id})
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/ask":
            self._handle_ask()
        else:
            self.send_error(404)

    def _serve_html(self):
        html = _load_template(self._site_name or self.site_id)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_ask(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(content_len)
            data = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, ValueError):
            self._json_response({"error": "Invalid JSON"}, 400)
            return

        question = (data.get("question") or "").strip()
        if not question:
            self._json_response({"error": "질문을 입력해 주세요."}, 400)
            return

        try:
            if self._runner is None:
                from src.demo import SiteDemoRunner

                self.__class__._runner = SiteDemoRunner(
                    site_id=self.site_id, provider=self.provider,
                )
            runner = self._runner

            if self.snapshot_path:
                result = runner.answer_from_snapshot(self.snapshot_path, question=question)
            else:
                result = runner.answer(question)

            self._json_response({
                "site_id": result.get("site_id"),
                "site_name": result.get("site_name"),
                "question": result.get("question"),
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "ok": result.get("ok", False),
                "snapshot_mode": result.get("snapshot_mode", False),
                "fallback_used": result.get("fallback_used", False),
                "warnings": result.get("warnings", []),
            })
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_app(
    site_id: str = "bukgu_gwangju",
    provider: str = "mock",
    snapshot: str | None = None,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> HTTPServer:
    """Create and return an HTTPServer for the mobile chat demo."""
    try:
        from src.site_profiles import load_profile
        profile = load_profile(site_id)
        site_name = profile.name
    except Exception:
        site_name = site_id

    handler = type("Handler", (MobileDemoHandler,), {
        "site_id": site_id,
        "provider": provider,
        "snapshot_path": snapshot,
        "_runner": None,
        "_site_name": site_name,
    })
    return HTTPServer((host, port), handler)
