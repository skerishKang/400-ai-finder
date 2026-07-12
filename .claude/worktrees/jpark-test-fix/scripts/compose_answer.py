#!/usr/bin/env python3
"""CLI entry point for Stage 6 answer composition.

Composes a grounded answer from Stage 5 search results JSON using
a configurable LLM provider.

Usage::

    # Default (mock provider)
    python scripts/compose_answer.py --search-results /tmp/search-results.json

    # Mock provider with file output
    python scripts/compose_answer.py \\
        --search-results /tmp/search-results.json \\
        --output /tmp/answer.json \\
        --markdown-output /tmp/answer.md

    # Specific provider
    python scripts/compose_answer.py \\
        --search-results /tmp/search-results.json \\
        --provider openai_compatible

    # KiloCode provider (using env vars from Hermes config)
    AI_FINDER_LLM_PROVIDER=kilocode \\
    python scripts/compose_answer.py \\
        --search-results /tmp/search-results.json
"""

from __future__ import annotations

import json
import os
import sys
import argparse

# Add project root to sys.path so src/ is importable
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.answer.answer_composer import AnswerComposer
from src.llm import get_provider, list_providers


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compose a grounded answer from search results using an LLM provider."
    )
    parser.add_argument(
        "--search-results",
        default=None,
        help="Path to Stage 5 search results JSON file",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help=(
            "LLM provider name (default: AI_FINDER_LLM_PROVIDER env var, or 'mock'). "
            "Available: mock, openai_compatible, mistral, opengateway, kilocode, nvidia, groq"
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to save the full answer JSON result",
    )
    parser.add_argument(
        "--markdown-output",
        default=None,
        help="Path to save only the answer_markdown as a .md file",
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=5,
        help="Maximum number of sources to include (default: 5)",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List all available providers and exit",
    )

    args = parser.parse_args()

    # --- List providers mode ---
    if args.list_providers:
        providers = list_providers()
        print("Available LLM providers:")
        print("=" * 60)
        for p in providers:
            key_status = "✓" if p["has_api_key"] else "✗"
            print(f"  {p['name']:20s}  {key_status}  {p['description']}")
            print(f"  {'':20s}     model: {p['default_model']}")
            print()
        sys.exit(0)

    # --- Validate arguments ---
    if not args.search_results:
        print("Error: --search-results is required (use --list-providers to see available providers)", file=sys.stderr)
        sys.exit(1)

    # --- Validate input file ---
    if not os.path.exists(args.search_results):
        print(
            f"Error: Search results file not found: {args.search_results}",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Read search results ---
    with open(args.search_results, "r", encoding="utf-8") as f:
        search_data = f.read()

    # --- Resolve provider (allow env override) ---
    provider_name = args.provider or os.environ.get("AI_FINDER_LLM_PROVIDER", "mock")
    provider = get_provider(provider_name)

    # --- Compose answer ---
    composer = AnswerComposer(
        provider=provider,
        max_sources=args.max_sources,
    )
    result = composer.compose(search_data)

    # --- Output ---
    json_output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_output)
        print(f"Answer saved to {args.output}")
    else:
        print(json_output)

    # --- Markdown output (optional extra) ---
    if args.markdown_output:
        md_dir = os.path.dirname(args.markdown_output)
        if md_dir and not os.path.exists(md_dir):
            os.makedirs(md_dir, exist_ok=True)
        with open(args.markdown_output, "w", encoding="utf-8") as f:
            f.write(result.get("answer_markdown", ""))
        print(f"Markdown saved to {args.markdown_output}")


if __name__ == "__main__":
    main()
