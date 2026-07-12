#!/usr/bin/env python3
"""CLI for real-site compatibility diagnostics.

Usage::

    # Default (requests provider)
    python scripts/diagnose_site.py --url "https://bukgu.gwangju.kr/"

    # Specific provider
    python scripts/diagnose_site.py --url "https://bukgu.gwangju.kr/" --provider requests

    # All providers
    python scripts/diagnose_site.py --url "https://bukgu.gwangju.kr/" --provider all

    # With output file
    python scripts/diagnose_site.py --url "https://bukgu.gwangju.kr/" --output /tmp/diag.json
"""

from __future__ import annotations

import json
import os
import sys
import argparse
from typing import Any

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.diagnostics import run_diagnostics


def _print_summary(result: dict[str, Any]) -> None:
    """Print a human-readable summary of diagnostics."""
    print(f"\n{'='*60}")
    print(f"  Site Diagnostics: {result['url']}")
    print(f"{'='*60}")
    print(f"  Fetched at: {result['fetched_at']}")

    for pname, pdata in result.get("providers", {}).items():
        status = pdata.get("status", "?")
        if status == "skipped":
            print(f"\n  [{pname}] ⏭ SKIPPED — {pdata.get('reason', '')}")
            continue

        ok = pdata.get("ok", False)
        status_icon = "✓" if ok else "✗"
        print(f"\n  [{pname}] {status_icon} status={pdata.get('status_code', '?')}")

        if not ok:
            print(f"          error: {pdata.get('error', '?')}")
            # Show crawler backup if available
            crawler = pdata.get("crawler_result")
            if crawler:
                print(f"          crawler backup: http={crawler.get('status_code')}, "
                      f"title={crawler.get('title', '')[:60]}")
            continue

        print(f"          title:     {pdata.get('title', '')[:80]}")
        print(f"          content:   text={pdata.get('text_length', 0)} chars, "
              f"html={pdata.get('html_length', 0)} chars")
        print(f"          links:     {pdata.get('link_count', '?')} total "
              f"(int={pdata.get('internal_links', '?')}, "
              f"ext={pdata.get('external_links', '?')}, "
              f"doc={pdata.get('document_links', '?')})")
        print(f"          encoding:  {pdata.get('html_analysis', {}).get('encoding', '?')}")

        ha = pdata.get("html_analysis", {})
        extra = []
        if ha.get("board_matches", 0) > 0:
            extra.append(f"board={ha['board_matches']}")
        if ha.get("php_legacy_hits", 0) > 0:
            extra.append(f"php={ha['php_legacy_hits']}")
        if ha.get("frame_count", 0) > 0 or ha.get("iframe_count", 0) > 0:
            extra.append(f"frame={ha.get('frame_count',0)} iframe={ha.get('iframe_count',0)}")
        if ha.get("script_count", 0) > 0:
            extra.append(f"scripts={ha['script_count']}")
        if ha.get("javascript_href_count", 0) > 0:
            extra.append(f"js_hrefs={ha['javascript_href_count']}")
        if ha.get("menu_keyword_hits", 0) > 0:
            extra.append(f"menu_keywords={ha['menu_keyword_hits']}")
        if extra:
            print(f"          signals:   {', '.join(extra)}")

        signals = pdata.get("signals", [])
        if signals:
            print(f"          flags:     {', '.join(signals)}")

    # Classifications
    classifications = result.get("classifications", [])
    print(f"\n{'='*60}")
    print(f"  Classifications ({len(classifications)}):")
    for c in classifications:
        print(f"    - {c}")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose real-site compatibility for AI-finder ingestion."
    )
    parser.add_argument("--url", required=True, help="Target URL to diagnose")
    parser.add_argument(
        "--provider",
        default=None,
        help="Fetch provider name, or 'all' for all available. Default: requests",
    )
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout (default: 15)")
    parser.add_argument("--output", default=None, help="Path to save the full JSON results")
    parser.add_argument(
        "--include-raw",
        action="store_true",
        default=False,
        help="Include raw fetch results in JSON output (default: false)",
    )
    parser.add_argument(
        "--max-preview-chars",
        type=int,
        default=1000,
        help="Max chars for text preview (default: 1000)",
    )

    args = parser.parse_args()

    # Resolve providers
    provider_arg = args.provider or os.environ.get("AI_FINDER_FETCH_PROVIDER", "requests")
    if provider_arg == "all":
        providers_to_test = ["requests", "mock"]
        # Add firecrawl if key is available
        if os.environ.get("FIRECRAWL_API_KEY"):
            providers_to_test.append("firecrawl")
    else:
        providers_to_test = [provider_arg]

    # Run diagnostics
    result = run_diagnostics(
        url=args.url,
        timeout=args.timeout,
        providers=providers_to_test,
    )

    # Print summary
    _print_summary(result)

    # Output full JSON
    if args.output:
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Full JSON saved to: {args.output}")


if __name__ == "__main__":
    main()
