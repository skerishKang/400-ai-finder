#!/usr/bin/env python3
"""run_mobile_demo.py — Start the mobile-first web demo server.

Usage::

    PYTHONPATH=. .venv/bin/python scripts/run_mobile_demo.py \\
        --site-id bukgu_gwangju \\
        --provider mock \\
        --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json

Then open http://localhost:8080 in a browser.
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Homepage Finder — Mobile-first web demo"
    )
    parser.add_argument(
        "--site-id",
        default="bukgu_gwangju",
        help="Site profile ID (default: bukgu_gwangju)",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="LLM provider name (default: None)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LLM model name/ID (default: None)",
    )
    parser.add_argument(
        "--preset",
        default=None,
        help="LLM model preset shortcut (default: None)",
    )
    parser.add_argument(
        "--snapshot",
        default=None,
        help="Path to snapshot JSON for stable demos (recommended)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Bind port (default: 8080)",
    )

    args = parser.parse_args()

    from src.web.mobile_demo import create_app
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

    server = create_app(
        site_id=args.site_id,
        provider=resolved_provider,
        model=resolved_model,
        snapshot=args.snapshot,
        host=args.host,
        port=args.port,
    )

    snap_tag = f" (snapshot: {args.snapshot})" if args.snapshot else " (live mode)"
    print()
    print("=" * 60)
    print(f"  🏛️  AI 홈페이지 도우미 — {args.site_id}")
    print("=" * 60)
    print(f"  URL:     http://localhost:{args.port}")
    print(f"  모드:    {'snapshot' if args.snapshot else 'live'}")
    print(f"  LLM:     {resolved_provider} (model: {resolved_model or 'default'})")
    print()
    print(f"  브라우저에서 http://localhost:{args.port} 를 열어주세요.")
    print(f"  Ctrl+C로 종료합니다.{snap_tag}")
    print("=" * 60)
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
        server.server_close()


if __name__ == "__main__":
    main()
