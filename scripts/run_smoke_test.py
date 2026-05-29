import os
import sys
import json
import argparse
from datetime import datetime
from urllib.parse import urlparse

# Add root directory to path to locate src packages
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.pipeline.smoke_reporter import SmokeTestRunner

def get_host_name(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc
        if ":" in host:
            host = host.split(":")[0]
        if host.startswith("www."):
            host = host[4:]
        if not host:
            return "target"
        return host
    except Exception:
        return "target"

def main():
    default_provider = os.environ.get("AI_FINDER_LLM_PROVIDER", "mock")
    
    parser = argparse.ArgumentParser(description="AI Finder Smoke Test Runner")
    parser.add_argument("--url", help="Target URL (required if --config is not specified)")
    parser.add_argument("--query", help="Target query (required if --config is not specified)")
    parser.add_argument("--name", help="Target name (optional)")
    parser.add_argument("--config", help="Path to config JSON containing target list")
    parser.add_argument("--provider", default=default_provider, help="LLM provider (default: mock)")
    parser.add_argument("--fetch-provider", default=os.environ.get("AI_FINDER_FETCH_PROVIDER"),
                        help="Fetch provider name (mock, requests, firecrawl). Default: requests (built-in)")
    parser.add_argument("--output-dir", help="Output directory for reports and raw runs")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-sources", type=int, default=5)
    parser.add_argument("--max-enrich-pages", type=int, default=10)
    parser.add_argument("--max-sitemap-urls", type=int, default=200)
    parser.add_argument("--max-sitemaps", type=int, default=10)
    parser.add_argument("--max-chars", type=int, default=12000)
    
    args = parser.parse_args()
    
    # 1. Config vs Single URL validation
    targets = []
    if args.config:
        if not os.path.exists(args.config):
            print(f"Error: Config file not found at {args.config}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                targets = config_data.get("targets", [])
        except Exception as e:
            print(f"Error parsing config file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if not args.url or not args.query:
            print("Error: Either --config must be specified, or both --url and --query are required.", file=sys.stderr)
            sys.exit(1)
            
        name = args.name
        if not name:
            name = get_host_name(args.url)
            
        targets = [{
            "name": name,
            "url": args.url,
            "query": args.query
        }]
        
    if not targets:
        print("Error: No targets found to run.", file=sys.stderr)
        sys.exit(1)
        
    # 2. Set output directory
    output_dir = args.output_dir
    if not output_dir:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = os.path.join("data", "runs", f"smoke-{timestamp}")
        
    # 3. Execute SmokeTestRunner
    runner = SmokeTestRunner(
        output_dir=output_dir,
        provider=args.provider,
        fetch_provider=args.fetch_provider,
        top_k=args.top_k,
        max_sources=args.max_sources,
        max_enrich_pages=args.max_enrich_pages,
        max_sitemap_urls=args.max_sitemap_urls,
        max_sitemaps=args.max_sitemaps,
        max_chars=args.max_chars
    )
    
    print(f"Starting smoke test batch runner...")
    print(f"Targets count: {len(targets)}")
    print(f"LLM Provider: {args.provider}")
    print(f"Fetch Provider: {args.fetch_provider or '(default: requests built-in)'}")
    print(f"Output directory: {output_dir}")
    print("-" * 50)
    
    batch_report = runner.run_targets(targets)
    
    print("-" * 50)
    print("Smoke Test Results Summary:")
    for t in batch_report["targets"]:
        status_str = "OK" if t["ok"] else "FAIL"
        warn_str = f" (Warnings: {', '.join(t['warnings'])})" if t["warnings"] else ""
        print(f"- [{status_str}] {t['name']} ({t['url']}){warn_str}")
        if t["error"]:
            print(f"  Error: {t['error']}", file=sys.stderr)
            
    print("-" * 50)
    print(f"JSON Report: {os.path.join(output_dir, 'smoke-report.json')}")
    print(f"Markdown Summary: {os.path.join(output_dir, 'smoke-report.md')}")
    
    if batch_report["ok"]:
        print("All targets executed successfully.")
        sys.exit(0)
    else:
        print("Some targets failed to execute.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
