#!/usr/bin/env python3
"""CLI entry point for the end-to-end pipeline runner.

Usage::

    python scripts/run_pipeline.py \
      --url "https://example.com" \
      --query "신청서 제출서류" \
      --provider mock
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pipeline.pipeline_runner import PipelineRunner, make_default_output_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Finder end-to-end pipeline runner",
    )
    parser.add_argument("--url", required=True, help="Target homepage URL")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument(
        "--provider",
        default=os.environ.get("AI_FINDER_LLM_PROVIDER", "mock"),
        help="LLM provider name (default: env AI_FINDER_LLM_PROVIDER or mock)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: data/runs/run-YYYYMMDD-HHMMSS)",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Search top_k (default: 5)")
    parser.add_argument("--max-sources", type=int, default=5, help="Max sources for answer (default: 5)")
    parser.add_argument("--max-enrich-pages", type=int, default=20, help="Max pages to enrich (default: 20)")
    parser.add_argument("--max-sitemap-urls", type=int, default=200, help="Max sitemap URLs (default: 200)")
    parser.add_argument("--max-sitemaps", type=int, default=10, help="Max sitemaps to parse (default: 10)")
    parser.add_argument("--max-chars", type=int, default=12000, help="Max chars for enrichment (default: 12000)")

    args = parser.parse_args()

    output_dir = args.output_dir or make_default_output_dir()

    runner = PipelineRunner(
        output_dir=output_dir,
        provider=args.provider,
        max_sitemap_urls=args.max_sitemap_urls,
        max_sitemaps=args.max_sitemaps,
        max_enrich_pages=args.max_enrich_pages,
        top_k=args.top_k,
        max_sources=args.max_sources,
        max_chars=args.max_chars,
    )

    result = runner.run(url=args.url, query=args.query)

    # Print summary
    print(f"\npipeline-result.json: {output_dir}/pipeline-result.json")
    print(f"answer.json:          {output_dir}/answer.json")
    print(f"answer.md:            {output_dir}/answer.md")

    if result["ok"]:
        print("\n--- Pipeline OK ---")
        markdown = result.get("answer_markdown", "")
        if markdown:
            print(f"\n{markdown}")
    else:
        print(f"\n--- Pipeline FAILED at step ---")
        print(f"error: {result['error']}")
        for step in result["steps"]:
            status = "OK" if step["ok"] else "FAIL"
            print(f"  [{status}] {step['name']}: {step.get('error', '')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
