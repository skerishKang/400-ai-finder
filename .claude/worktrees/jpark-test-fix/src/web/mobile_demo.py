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
from http.server import ThreadingHTTPServer as HTTPServer, BaseHTTPRequestHandler
from typing import Any
from urllib.parse import urlparse

from src.demo.conversation_log import log_conversation
from src.fetch.sanitization import (
    SAFE_FAILURE_MESSAGE,
    sanitize_fetch_diagnostic,
    sanitize_warnings,
)
from src.llm.runtime_status import resolve_llm_runtime_status

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
    model: str | None = None
    snapshot_path: str | None = None
    pipeline_timeout_s: float | None = None
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
            reuse_runner = False
            if self._runner is not None:
                is_mock = hasattr(self._runner, "_mock_return_value") or "Mock" in type(self._runner).__name__
                if is_mock:
                    reuse_runner = True
                elif getattr(self._runner, "provider", None) == self.provider and getattr(self._runner, "model", None) == self.model:
                    reuse_runner = True

            if not reuse_runner:
                from src.demo import SiteDemoRunner
                self.__class__._runner = SiteDemoRunner(
                    site_id=self.site_id,
                    provider=self.provider,
                    model=self.model,
                    pipeline_timeout_s=self.pipeline_timeout_s,
                )
            runner = self._runner

            if self.snapshot_path:
                result = runner.answer_from_snapshot(self.snapshot_path, question=question)
            else:
                result = runner.answer(question)

            answer = result.get("answer", "")
            if not answer:
                answer = "지금은 답변 생성이 어렵습니다. 먼저 아래 출처를 확인해 보세요."

            response_data = {
                "site_id": result.get("site_id"),
                "site_name": result.get("site_name"),
                "question": result.get("question"),
                "answer": answer,
                "sources": result.get("sources", []),
                "ok": result.get("ok", False),
                "answer_ok": result.get("answer_ok", False),
                "answer_status": result.get("answer_status", "error"),
                "provider": result.get("provider", ""),
                "model": result.get("model", ""),
                "snapshot_mode": result.get("snapshot_mode", False),
                "fallback_used": result.get("fallback_used", False),
                "llm_live": result.get("llm_live", False),
                "llm_status": result.get("llm_status", "unknown"),
                "llm_label": result.get("llm_label", ""),
                "warnings": sanitize_warnings(result.get("warnings", [])),
                "route": result.get("route", "site_search"),
                "should_search_site": bool(result.get("should_search_site", True)),
                "route_confidence": float(result.get("route_confidence", 0.0)),
                "route_reason": result.get("route_reason", ""),
                "search_query": result.get("search_query", ""),
                "answer_mode": result.get("answer_mode", "retrieval_answer"),
                "source_weak": bool(result.get("source_weak", False)),
                # Stage #801: closed-vocabulary fetch diagnostic. The
                # runner emits ``None`` for direct_answer / clarify /
                # snapshot paths and a small dict with category /
                # short_reason / retry_hint / is_transient on failure
                # paths. Callers must never echo raw exception text,
                # headers, bodies, or URLs in this field.
                "fetch_diagnostic": sanitize_fetch_diagnostic(result.get("fetch_diagnostic")),
            }
            if not log_conversation(response_data):
                response_data["warnings"] = sanitize_warnings(
                    list(response_data.get("warnings", [])) + ["conversation log write failed"]
                )
            self._json_response(response_data)
        except Exception:
            safe_warning = SAFE_FAILURE_MESSAGE
            llm_status = resolve_llm_runtime_status(
                provider=self.provider,
                model=self.model,
                ok=False,
                warnings=[safe_warning],
                snapshot_mode=bool(self.snapshot_path),
            )
            response_data = {
                "site_id": self.site_id,
                "site_name": self._site_name or self.site_id,
                "question": question,
                "answer": "제가 확인한 자료 기준으로는 관련 메뉴가 가장 먼저 필요해 보입니다. 아래 출처를 먼저 확인해 보세요.",
                "sources": [],
                "ok": False,
                "answer_ok": False,
                "answer_status": "error",
                "provider": self.provider,
                "model": self.model or "",
                "snapshot_mode": bool(self.snapshot_path),
                "fallback_used": False,
                "llm_live": llm_status["llm_live"],
                "llm_status": llm_status["llm_status"],
                "llm_label": llm_status["llm_label"],
                "warnings": [safe_warning],
                "route": "site_search",
                "should_search_site": True,
                "route_confidence": 0.0,
                "route_reason": "outer_exception",
                "search_query": "",
                "answer_mode": "retrieval_answer",
                "source_weak": True,
                "fetch_diagnostic": None,
            }
            if not log_conversation(response_data):
                response_data["warnings"] = sanitize_warnings(
                    list(response_data.get("warnings", [])) + ["conversation log write failed"]
                )
            self._json_response(response_data)

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
    model: str | None = None,
    pipeline_timeout_s: float | None = None,
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
        "model": model,
        "snapshot_path": snapshot,
        "pipeline_timeout_s": pipeline_timeout_s,
        "_runner": None,
        "_site_name": site_name,
    })
    return HTTPServer((host, port), handler)
