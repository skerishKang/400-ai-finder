"""Static file server for web UI assets.

Serves files from ``src/web/static/`` under the ``/static/`` URL prefix.
Uses standard library only — no external dependencies.

This is a development-grade static server for local demos and is **not
suitable for production**. Path resolution is hardened against directory
traversal, encoded bypasses, absolute-path injection, and symlink escapes,
but it is not intended to face untrusted networks.

Usage inside a BaseHTTPRequestHandler::

    from .static_server import is_static_request, serve_static

    def do_GET(self):
        if is_static_request(self.path):
            serve_static(self)
            return
        # ... normal routing
"""

from __future__ import annotations

import mimetypes
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_ROOT = os.path.join(_THIS_DIR, "static")

# Ensure mimetypes knows common web extensions
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("text/javascript", ".js")


def _url_path_only(path: str) -> str:
    """Return the URL path without query string or fragment."""
    return path.split("?", 1)[0].split("#", 1)[0]


def is_static_request(path: str) -> bool:
    """Return True if *path* is a static-file request (``/static/...``).

    The ``".." not in path`` check is an auxiliary fast-reject only. The final
    security decision is made inside :func:`serve_static` using ``realpath``
    resolution, so an attempted traversal is blocked even if this helper were
    bypassed.
    """
    url_path = _url_path_only(path)
    return url_path.startswith("/static/") and ".." not in url_path


def _is_within_base(requested_real: str, base_real: str) -> bool:
    """Return True iff *requested_real* is *base_real* itself or a descendant.

    Uses an exact match or a proper separator boundary to avoid the classic
    prefix-confusion bug (e.g. ``/srv/static`` matching ``/srv/static-evil``).
    """
    if requested_real == base_real:
        return True
    return requested_real.startswith(base_real + os.sep)


def serve_static(handler) -> None:
    """Serve a static file in response to *handler*'s request.

    Call from ``do_GET`` after :func:`is_static_request` returns True.
    Sends 200 with the correct Content-Type on success, 404 on missing file
    or on any path that resolves outside ``STATIC_ROOT``.
    """
    path = _url_path_only(handler.path)
    # Strip the /static/ prefix and neutralize any leading slashes so that an
    # injected absolute path (e.g. "/etc/passwd") is treated as relative.
    relative = path[len("/static/"):].lstrip("/")
    candidate = os.path.normpath(os.path.join(STATIC_ROOT, relative))

    # Resolve the real on-disk location, collapsing "..", symlinks, and any
    # mixed separators, then compare against the real STATIC_ROOT boundary.
    base_real = os.path.realpath(STATIC_ROOT)
    requested_real = os.path.realpath(candidate)

    if not _is_within_base(requested_real, base_real):
        handler.send_error(404)
        return

    # Final re-check before opening: the resolved target must be a regular
    # file that still lives under the real STATIC_ROOT boundary.
    if not os.path.isfile(requested_real):
        handler.send_error(404)
        return

    content_type, _ = mimetypes.guess_type(requested_real)
    if content_type is None:
        content_type = "application/octet-stream"

    try:
        with open(requested_real, "rb") as f:
            body = f.read()
        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except OSError:
        handler.send_error(404)
