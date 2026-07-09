#!/usr/bin/env python3
"""run_all_demos.py — Start both mobile and admin demo servers.

Runs the mobile user demo and desktop admin dashboard simultaneously,
printing access URLs for presentation.

Usage::

    PYTHONPATH=. .venv/bin/python scripts/run_all_demos.py \\
        --site-id bukgu_gwangju \\
        --provider mock \\
        --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json

Options::

    --mobile-port   Mobile demo port (default: 8400)
    --admin-port    Admin dashboard port (default: 8090)
    --host          Bind host (default: 0.0.0.0)
    --pipeline-timeout-s  Wall-clock budget for the site_search pipeline.
                         When the upstream fetch hangs past this value, the
                         demo returns a structured soft-JSON response
                         (route=site_search, ok=false, source_weak=true)
                         instead of blocking the HTTP request. Default 30s;
                         lower it (e.g. ``1``) for offline / controlled
                         smoke runs where the homepage is unreachable.
"""

from __future__ import annotations

import argparse
import signal
import sys
import os
import threading

# Load environment variables from .env files before any imports that need them.
# python-dotenv handles both "KEY=value" and "export KEY=value" formats.
# Load Hermes env first (actual API keys), then project env (resolves ${VAR} refs).
from dotenv import load_dotenv

_load_dotenv_hermes = load_dotenv('/root/.hermes/.env')
_load_dotenv_project = load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_server(server, name: str):
    """Run a server in a thread."""
    try:
        server.serve_forever()
    except Exception as e:
        print(f"[{name}] Error: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Homepage Finder — Run all demo servers"
    )
    parser.add_argument("--site-id", required=True, help="Site profile ID")
    parser.add_argument("--provider", default=None, help="LLM provider (default: None)")
    parser.add_argument("--model", default=None, help="LLM model (default: None)")
    parser.add_argument("--preset", default=None, help="LLM model preset shortcut (default: None)")
    parser.add_argument("--snapshot", default=None, help="Path to snapshot JSON")
    parser.add_argument("--mobile-port", type=int, default=8400, help="Mobile demo port")
    parser.add_argument("--admin-port", type=int, default=8090, help="Admin dashboard port")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument(
        "--pipeline-timeout-s",
        type=float,
        default=30.0,
        help=(
            "Wall-clock budget (seconds) for the site_search pipeline. "
            "When the upstream fetch hangs past this value, the demo "
            "returns a structured soft-JSON response instead of "
            "blocking. Default: 30.0."
        ),
    )
    args = parser.parse_args()

    from src.web.mobile_demo import create_app
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

    # Create servers
    mobile_server = create_app(
        site_id=args.site_id,
        provider=resolved_provider,
        model=resolved_model,
        snapshot=args.snapshot,
        host=args.host,
        port=args.mobile_port,
        pipeline_timeout_s=args.pipeline_timeout_s,
    )

    admin_server = create_admin_app(
        site_id=args.site_id,
        provider=resolved_provider,
        model=resolved_model,
        snapshot=args.snapshot,
        host=args.host,
        port=args.admin_port,
        pipeline_timeout_s=args.pipeline_timeout_s,
    )

    # Print banner
    print("=" * 50)
    print("  AI 홈페이지 파인더 — 데모 서버")
    print("=" * 50)
    print()
    print(f"  사이트: {args.site_id}")
    print(f"  LLM: {resolved_provider} (model: {resolved_model or 'default'})")
    if args.snapshot:
        print(f"  Snapshot: {args.snapshot}")
    print(f"  Pipeline timeout: {args.pipeline_timeout_s}s")
    print()
    print(f"  📱 모바일 사용자 화면: http://localhost:{args.mobile_port}")
    print(f"  🖥️  운영자 대시보드:   http://localhost:{args.admin_port}")
    print()
    print("  Ctrl+C로 모두 종료")
    print("=" * 50)
    print()

    # Start servers in threads
    mobile_thread = threading.Thread(
        target=run_server, args=(mobile_server, "mobile"), daemon=True
    )
    admin_thread = threading.Thread(
        target=run_server, args=(admin_server, "admin"), daemon=True
    )
    mobile_thread.start()
    admin_thread.start()

    # Handle shutdown
    def shutdown(sig, frame):
        print("\n종료 중...")
        mobile_server.shutdown()
        admin_server.shutdown()
        mobile_server.server_close()
        admin_server.server_close()
        print("완료.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep main thread alive
    try:
        mobile_thread.join()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
