import os
import sys
import json
import argparse
from src.search.keyword_searcher import KeywordSearcher

def main():
    parser = argparse.ArgumentParser(description="Search index using keywords.")
    parser.add_argument("--index", required=True, help="Path to the JSONL enriched index file")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--top-k", type=int, default=5, help="Number of top results to return (default: 5)")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--content-type", help="Filter by content type")
    parser.add_argument("--output", help="Path to save search results in JSON")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.index):
        print(f"Error: Index file does not exist: {args.index}", file=sys.stderr)
        sys.exit(1)
        
    searcher = KeywordSearcher(args.index)
    
    if searcher.errors:
        for err in searcher.errors:
            print(f"Warning: {err}", file=sys.stderr)
            
    results = searcher.search(
        query=args.query,
        top_k=args.top_k,
        category=args.category,
        content_type=args.content_type
    )
    
    output_data = {
        "query": args.query,
        "top_k": args.top_k,
        "filters": {
            "category": args.category or "",
            "content_type": args.content_type or ""
        },
        "result_count": len(results),
        "results": results
    }
    
    json_result = json.dumps(output_data, ensure_ascii=False, indent=2)
    
    if args.output:
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_result)
        print(f"Search results saved to {args.output}")
    else:
        print(json_result)

if __name__ == "__main__":
    main()
