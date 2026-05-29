import os
import sys
import json
import argparse

# Add the project root directory to the python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.crawler.url_crawler import URLCrawler

def main():
    parser = argparse.ArgumentParser(description="Analyze a single URL and extract metadata/links.")
    parser.add_argument("--url", required=True, help="The URL to analyze")
    parser.add_argument("--max-chars", type=int, default=8000, help="Maximum body text characters to extract")
    parser.add_argument("--output", help="Output path to save the JSON result")
    
    args = parser.parse_args()
    
    crawler = URLCrawler()
    result = crawler.analyze(args.url, max_chars=args.max_chars)
    
    json_result = json.dumps(result, ensure_ascii=False, indent=2)
    
    if args.output:
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_result)
        print(f"Results saved to {args.output}")
    else:
        print(json_result)

if __name__ == "__main__":
    main()
