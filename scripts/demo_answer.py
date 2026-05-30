#!/usr/bin/env python3
"""demo_answer.py — CLI for the grounded answer demo runner.

Usage::

    PYTHONPATH=. .venv/bin/python scripts/demo_answer.py \\
        --site-id bukgu_gwangju \\
        --question "민원서식 어디서 받아?" \\
        --provider mock
"""

from __future__ import annotations

import argparse
import json
import sys
import os

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Finder — Grounded answer demo for a site profile"
    )
    parser.add_argument(
        "--site-id",
        required=True,
        help="Site profile ID (e.g. bukgu_gwangju)",
    )
    parser.add_argument(
        "--question",
        required=True,
        help="Natural-language question (e.g. '민원서식 어디서 받아?')",
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
        "--fetch-provider",
        default=None,
        help="Fetch provider name (default: from profile, e.g. requests)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to save the JSON result (optional)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-K search results (default: 5)",
    )
    parser.add_argument(
        "--snapshot",
        default=None,
        help="Path to a snapshot JSON file — use cached data instead of live fetch",
    )
    parser.add_argument(
        "--save-snapshot",
        default=None,
        help="Path to save the live result as a reusable snapshot",
    )

    args = parser.parse_args()

    # Lazy import so CLI help is fast
    from src.demo import run_demo
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

    result = run_demo(
        site_id=args.site_id,
        question=args.question,
        provider=resolved_provider,
        model=resolved_model,
        fetch_provider=args.fetch_provider,
        top_k=args.top_k,
        snapshot=args.snapshot,
        save_snapshot=args.save_snapshot,
    )

    # Print console-friendly output
    _print_result(result)

    # Save JSON if requested
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n📄 JSON result saved to: {args.output}")


def _print_result(result: dict) -> None:
    """Pretty-print demo result to console."""
    sep = "=" * 60
    sub = "-" * 40

    print()
    print(sep)
    print(f"  🏛️  {result.get('site_name', '?')}  ({result.get('site_id', '?')})")
    print(sep)
    print(f"  질문:      {result.get('question', '?')}")
    print(f"  LLM:       {result.get('provider', '?')}")
    mode_tag = "  [snapshot]" if result.get("snapshot_mode") else ""
    print(f"  Fetch:     {result.get('fetch_provider', '?')}{mode_tag}")
    ok = result.get("ok", False)
    answer_ok = result.get("answer_ok", False)
    print(f"  Pipeline:  {'✅ 성공' if ok else '❌ 실패'}")
    print(f"  답변:      {'✅ 생성됨' if answer_ok else '❌ 없음'}")
    print(f"  검색결과:  {len(result.get('search_results', []))}건")
    print(f"  출처:      {len(result.get('sources', []))}건")
    print()

    # Warnings
    warnings = result.get("warnings", [])
    if warnings:
        print("  ⚠️  경고:")
        for w in warnings:
            print(f"       • {w}")
        print()

    # Sources
    sources = result.get("sources", [])
    if sources:
        print(f"  📎 출처 ({len(sources)}건)")
        print(sub)
        for i, src in enumerate(sources[:5], 1):
            title = (src.get("title") or "")[:80]
            url = src.get("url", "")
            snippet = (src.get("snippet") or "")[:120]
            print(f"  [{i}] {title}")
            if url:
                print(f"      URL: {url}")
            if snippet:
                print(f"      → {snippet}")
            print()

    # Answer preview
    answer = result.get("answer", "")
    if answer:
        print(f"  💬 답변 미리보기 ({len(answer)} chars)")
        print(sub)
        # Show first 500 chars
        preview = answer[:500]
        print(preview)
        if len(answer) > 500:
            print("  ... (truncated)")
        print()

    print(sep)


if __name__ == "__main__":
    main()
