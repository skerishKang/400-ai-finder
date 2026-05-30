#!/usr/bin/env python3
"""run_admin_demo.py — Start the desktop admin dashboard.

Usage::

    PYTHONPATH=. .venv/bin/python scripts/run_admin_demo.py \\
        --site-id bukgu_gwangju \\
        --provider mock \\
        --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json \\
        --port 8090
"""

from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Homepage Finder — Admin dashboard"
    )
    parser.add_argument("--site-id", required=True, help="Site profile ID")
    parser.add_argument("--provider", default="mock", help="LLM provider (default: mock)")
    parser.add_argument("--model", default=None, help="LLM model (default: None)")
    parser.add_argument("--preset", default=None, help="LLM model preset shortcut (default: None)")
    parser.add_argument("--snapshot", default=None, help="Path to snapshot JSON")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8090, help="Bind port (default: 8090)")
    args = parser.parse_args()

    from src.web.admin_demo import create_admin_app
    from src.llm import resolve_provider_model

    try:
        resolved_provider, resolved_model = resolve_provider_model(
            model=args.model,
            provider=args.provider,
            preset=args.preset,
        )
    except ValueError as e:
        print(f"Error resolving LLM: {e}", file=sys.stderr)
        sys.exit(1)

    server = create_admin_app(
        site_id=args.site_id,
        provider=resolved_provider,
        model=resolved_model,
        snapshot=args.snapshot,
        host=args.host,
        port=args.port,
    )

    print(f"Admin dashboard: http://localhost:{args.port}")
    print(f"Site: {args.site_id}")
    print(f"LLM: {resolved_provider} (model: {resolved_model or 'default'})")
    if args.snapshot:
        print(f"Snapshot: {args.snapshot}")
    print("Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
