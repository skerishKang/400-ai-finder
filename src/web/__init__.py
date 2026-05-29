"""Mobile-first web demo for AI Homepage Finder.

Serves a responsive mobile UI at http://localhost:8080 with a
POST /api/ask endpoint that returns demo results from SiteDemoRunner.

Usage::

    from src.web.mobile_demo import create_app
    app = create_app(site_id="bukgu_gwangju", snapshot="/tmp/snap.json")
    app.serve_forever()
"""

from __future__ import annotations

from .mobile_demo import create_app

__all__ = ["create_app"]
