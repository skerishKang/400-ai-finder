"""Desktop admin/operator dashboard for AI Homepage Finder.

Serves a desktop-focused admin UI at http://localhost:8090 with
site profile, snapshot status, and demo question testing.

Usage::

    from src.web.admin_demo import create_admin_app
    app = create_admin_app(site_id="bukgu_gwangju", snapshot="/tmp/snap.json")
    app.serve_forever()
"""

from __future__ import annotations

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any
from urllib.parse import urlparse

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(_THIS_DIR, "templates", "admin_demo.html")


def _load_template() -> str:
    """Load the admin HTML template."""
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"""<!DOCTYPE html><html lang="ko"><body>
<h1>Template not found</h1><p>{TEMPLATE_PATH}</p></body></html>"""


class AdminDemoHandler(BaseHTTPRequestHandler):
    """HTTP handler for the admin dashboard."""

    site_id: str = "bukgu_gwangju"
    provider: str = "mock"
    model: str | None = None
    snapshot_path: str | None = None
    _runner: Any = None
    _site_name: str = ""
    _profile_data: dict[str, Any] | None = None
    _snapshot_data: dict[str, Any] | None = None
    _runner_cache: dict[tuple, Any] = {}  # (site_id, provider, model) -> runner

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
        elif parsed.path == "/api/info":
            self._handle_info()
        elif parsed.path == "/health":
            self._json_response({"ok": True, "site_id": self.site_id})
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/test":
            self._handle_test()
        else:
            self.send_error(404)

    def _serve_html(self):
        body = _load_template().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_info(self):
        info: dict[str, Any] = {"summary": {}, "profile": {}, "snapshot": {}, "status": {}}
        
        from src.llm.model_presets import PRESETS
        resolved_preset = None
        recommended_order = None
        for p_name, p_info in PRESETS.items():
            if p_info["provider"] == self.provider and p_info["model"] == (self.model or ""):
                resolved_preset = p_name
                recommended_order = p_info["recommended_order"]
                break

        info["summary"] = {
            "service_name": "AI 홈페이지 파인더",
            "site_id": self.site_id,
            "site_name": self._site_name,
            "provider": self.provider,
            "model": self.model or "",
            "preset": resolved_preset or "-",
            "recommended_order": recommended_order or "-",
            "fetch_provider": "-",
            "snapshot_path": self.snapshot_path or "",
        }
        profile = self._get_profile_data()
        if profile:
            info["profile"] = profile
            info["summary"]["fetch_provider"] = profile.get("preferred_fetch_provider", "-")
        snap = self._get_snapshot_data()
        if snap:
            nav_count = len(
                snap.get("homepage_map", {})
                .get("homepage", {})
                .get("navigation_links", [])
            )
            info["snapshot"] = {
                "loaded": True,
                "path": self.snapshot_path,
                "fetched_at": snap.get("fetched_at", "-"),
                "nav_link_count": nav_count,
                "source_count": len(snap.get("sources", [])),
                "question": snap.get("question", "-"),
            }
            info["status"]["snapshot_mode"] = snap.get("snapshot_mode", False)
        else:
            info["snapshot"] = {"loaded": False, "path": self.snapshot_path or ""}

        # Available site profiles list
        from src.site_profiles import list_profiles
        info["profiles"] = list_profiles()

        self._json_response(info)

    def _handle_test(self):
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

        # site_id override from payload (admin can switch sites)
        req_site_id = (data.get("site_id") or "").strip()
        effective_site_id = req_site_id if req_site_id else self.site_id

        # Validate site_id exists
        if req_site_id:
            try:
                from src.site_profiles import load_profile
                test_profile = load_profile(req_site_id)
            except FileNotFoundError:
                self._json_response({"error": f"Unknown site_id: {req_site_id}"}, 400)
                return

        # Dynamically resolve preset/model/provider from payload
        req_provider = data.get("provider")
        req_model = data.get("model")
        req_preset = data.get("preset")

        from src.llm import resolve_provider_model
        try:
            resolved_provider, resolved_model = resolve_provider_model(
                model=req_model,
                provider=req_provider,
                preset=req_preset,
            )
        except Exception as e:
            # Fallback to defaults if resolution fails
            resolved_provider = req_provider or self.provider
            resolved_model = req_model or self.model

        # Snapshot resolution: use site-specific snapshot if available
        effective_snapshot = self.snapshot_path
        if req_site_id and req_site_id != self.site_id:
            # Try to find a snapshot for the requested site_id
            import glob as _glob
            fixture_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "..", "tests", "fixtures"
            )
            candidates = _glob.glob(os.path.join(fixture_dir, f"{req_site_id}_demo_snapshot.json"))
            effective_snapshot = candidates[0] if candidates else None

        try:
            # Runner cache: reuse if (site_id, provider, model) matches
            cache_key = (effective_site_id, resolved_provider, resolved_model or "")
            cached_runner = self._runner_cache.get(cache_key)
            reuse_runner = False
            if cached_runner is not None:
                is_mock = hasattr(cached_runner, "_mock_return_value") or "Mock" in type(cached_runner).__name__
                if is_mock:
                    reuse_runner = True
                else:
                    reuse_runner = True

            if not reuse_runner:
                from src.demo import SiteDemoRunner
                cached_runner = SiteDemoRunner(
                    site_id=effective_site_id,
                    provider=resolved_provider,
                    model=resolved_model,
                )
                self._runner_cache[cache_key] = cached_runner

            runner = cached_runner

            if effective_snapshot:
                result = runner.answer_from_snapshot(effective_snapshot, question=question)
            else:
                result = runner.answer(question)

            from src.llm.model_presets import PRESETS
            resolved_preset = None
            recommended_order = None
            for p_name, p_info in PRESETS.items():
                if p_info["provider"] == resolved_provider and p_info["model"] == (resolved_model or ""):
                    resolved_preset = p_name
                    recommended_order = p_info["recommended_order"]
                    break

            self._json_response({
                "site_id": result.get("site_id"),
                "site_name": result.get("site_name"),
                "question": result.get("question"),
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "search_results": result.get("search_results", []),
                "ok": result.get("ok", False),
                "answer_ok": result.get("answer_ok", False),
                "provider": result.get("provider", ""),
                "model": result.get("model", ""),
                "preset": resolved_preset or "-",
                "recommended_order": recommended_order or "-",
                "snapshot_mode": result.get("snapshot_mode", False),
                "fallback_used": result.get("fallback_used", False),
                "warnings": result.get("warnings", []),
            })
        except Exception as e:
            from src.llm.model_presets import PRESETS
            resolved_preset = None
            recommended_order = None
            for p_name, p_info in PRESETS.items():
                if p_info["provider"] == resolved_provider and p_info["model"] == (resolved_model or ""):
                    resolved_preset = p_name
                    recommended_order = p_info["recommended_order"]
                    break
            # Resolve site name for error response
            error_site_name = effective_site_id
            try:
                from src.site_profiles import load_profile as _lp
                error_site_name = _lp(effective_site_id).name
            except Exception:
                pass
            self._json_response({
                "site_id": effective_site_id,
                "site_name": error_site_name,
                "question": question,
                "answer": "",
                "sources": [],
                "search_results": [],
                "ok": False,
                "answer_ok": False,
                "provider": resolved_provider,
                "model": resolved_model or "",
                "preset": resolved_preset or "-",
                "recommended_order": recommended_order or "-",
                "snapshot_mode": bool(effective_snapshot),
                "fallback_used": False,
                "warnings": [f"Error: {e}"],
                "error": str(e),
            })

    def _get_profile_data(self) -> dict[str, Any] | None:
        if self._profile_data is not None:
            return self._profile_data
        try:
            from src.site_profiles import load_profile
            profile = load_profile(self.site_id)
            self.__class__._profile_data = {
                "name": profile.name,
                "base_url": profile.base_url,
                "classification": profile.classification,
                "preferred_fetch_provider": profile.preferred_fetch_provider,
                "important_keywords": profile.important_keywords,
                "fallback_strategy": profile.fallback_strategy,
            }
            return self._profile_data
        except Exception:
            return None

    def _get_snapshot_data(self) -> dict[str, Any] | None:
        if self._snapshot_data is not None:
            return self._snapshot_data
        if not self.snapshot_path:
            return None
        try:
            from src.demo import SiteDemoRunner
            self.__class__._snapshot_data = SiteDemoRunner.load_snapshot(self.snapshot_path)
            return self._snapshot_data
        except Exception:
            return None

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_admin_app(
    site_id: str = "bukgu_gwangju",
    provider: str = "mock",
    snapshot: str | None = None,
    host: str = "0.0.0.0",
    port: int = 8090,
    model: str | None = None,
) -> HTTPServer:
    """Create and return an HTTPServer for the admin dashboard."""
    try:
        from src.site_profiles import load_profile
        profile = load_profile(site_id)
        site_name = profile.name
    except Exception:
        site_name = site_id
    handler = type("AdminHandler", (AdminDemoHandler,), {
        "site_id": site_id,
        "provider": provider,
        "model": model,
        "snapshot_path": snapshot,
        "_runner": None,
        "_site_name": site_name,
        "_profile_data": None,
        "_snapshot_data": None,
    })
    return HTTPServer((host, port), handler)
