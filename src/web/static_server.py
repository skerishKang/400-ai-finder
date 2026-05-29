"""Static file server for web UI assets.

Serves files from ``src/web/static/`` under the ``/static/`` URL prefix.
Uses standard library only — no external dependencies.

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


def is_static_request(path: str) -> bool:
    """Return True if *path* is a static-file request (``/static/...``)."""
    return path.startswith("/static/") and ".." not in path


def serve_static(handler) -> None:
    """Serve a static file in response to *handler*'s request.

    Call from ``do_GET`` after :func:`is_static_request` returns True.
    Sends 200 with the correct Content-Type on success, 404 on missing file.
    """
    path = handler.path
    # Strip the /static/ prefix
    relative = path[len("/static/"):].lstrip("/")
    file_path = os.path.normpath(os.path.join(STATIC_ROOT, relative))

    # Security: ensure the resolved path is under STATIC_ROOT
    if not file_path.startswith(os.path.normpath(STATIC_ROOT)):
        handler.send_error(404)
        return

    if not os.path.isfile(file_path):
        handler.send_error(404)
        return

    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = "application/octet-stream"

    try:
        with open(file_path, "rb") as f:
            body = f.read()
        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except OSError:
        handler.send_error(404)
