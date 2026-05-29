#!/usr/bin/env python3
"""CLI for fetching a single URL using a configurable fetch provider.

Usage::

    # Default (requests provider)
    python scripts/fetch_url.py --url "https://bukgu.gwangju.kr/"

    # Mock provider
    python scripts/fetch_url.py --url "https://bukgu.gwangju.kr/" --provider mock

    # Firecrawl provider (requires FIRECRAWL_API_KEY env var)
    python scripts/fetch_url.py --url "https://bukgu.gwangju.kr/" --provider firecrawl

    # With output file
    python scripts/fetch_url.py --url "https://bukgu.gwangju.kr/" --output /tmp/result.json
"""

from __future__ import annotations

import json
import os
import sys
import argparse

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.fetch import get_fetch_provider, list_fetch_providers


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch a single URL using a configurable fetch provider."
    )
    parser.add_argument(
        "--url",
        required=True,
        help="The URL to fetch",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help=(
            "Fetch provider (default: AI_FINDER_FETCH_PROVIDER env var, or 'requests'). "
            "Available: mock, requests, firecrawl"
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to save the fetch result JSON",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Request timeout in seconds",
    )
    parser.add_argument(
        "--include-raw",
        action="store_true",
        default=False,
        help="Include raw API response in output (default: false)",
    )
    parser.add_argument(
        "--max-preview-chars",
        type=int,
        default=1000,
        help="Max characters for text/markdown preview in console output (default: 1000)",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List all available fetch providers and exit",
    )

    args = parser.parse_args()

    # --- List providers mode ---
    if args.list_providers:
        providers = list_fetch_providers()
        print("Available fetch providers:")
        print("=" * 50)
        for p in providers:
            key_status = "✓" if p["has_api_key"] else "✗"
            print(f"  {p['name']:20s}  {key_status}")
        sys.exit(0)

    # --- Resolve provider ---
    provider_name = args.provider or os.environ.get(
        "AI_FINDER_FETCH_PROVIDER", "requests"
    )
    provider = get_fetch_provider(
        provider_name,
        timeout=args.timeout,
    )

    # --- Fetch ---
    try:
        result = provider.fetch(args.url, timeout=args.timeout)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Build output dict ---
    output = {
        "ok": result.ok,
        "provider": result.provider,
        "url": result.url,
        "status_code": result.status_code,
        "content_type": result.content_type,
        "title": result.title,
        "description": result.description,
        "text_preview": result.text[: args.max_preview_chars]
        if result.text
        else "",
        "markdown_preview": result.markdown[: args.max_preview_chars]
        if result.markdown
        else "",
        "links_count": len(result.links),
        "links": result.links,
        "fetched_at": result.fetched_at,
        "error": result.error,
    }

    # --- Include raw only if explicitly requested ---
    if args.include_raw:
        output["raw"] = result.raw

    json_output = json.dumps(output, ensure_ascii=False, indent=2)

    # --- Console summary ---
    status = "✓" if result.ok else "✗"
    print(f"Fetch result: {status}")
    print(f"  Provider:    {result.provider}")
    print(f"  URL:         {result.url}")
    print(f"  Status:      {result.status_code}")
    print(f"  ContentType: {result.content_type}")
    print(f"  Title:       {result.title}")
    if result.description:
        print(f"  Description: {result.description[:200]}")
    if result.text:
        print(f"  Text len:    {len(result.text)} chars (preview: {min(len(result.text), args.max_preview_chars)} shown)")
    if result.markdown:
        print(f"  Markdown:    {len(result.markdown)} chars")
    print(f"  Links:       {len(result.links)}")
    if result.error:
        print(f"  Error:       {result.error}")
    print(f"  Fetched at:  {result.fetched_at}")

    # --- Output file ---
    if args.output:
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_output)
        print(f"\nJSON saved to: {args.output}")
    else:
        print(f"\nFull JSON:\n{json_output}")


if __name__ == "__main__":
    main()
