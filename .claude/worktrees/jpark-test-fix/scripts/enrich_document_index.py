import os
import sys
import json
import argparse
from src.indexer.document_enricher import DocumentEnricher

def read_jsonl(filepath):
    docs = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs

def write_jsonl(docs, filepath):
    output_dir = os.path.dirname(filepath)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

def generate_summary(docs, input_path, output_path, summary_path, stats):
    md = []
    md.append("# 문서 본문 보강 요약")
    md.append("")
    md.append("## 입력")
    md.append("")
    md.append(f"- Document index: {input_path}")
    md.append("")
    md.append("## 출력")
    md.append("")
    md.append(f"- Enriched index: {output_path}")
    md.append("")
    md.append("## 통계")
    md.append("")
    md.append(f"- total: {stats['total']}")
    md.append(f"- fetched: {stats['fetched']}")
    md.append(f"- skipped: {stats['skipped']}")
    md.append(f"- error: {stats['error']}")
    md.append(f"- not_processed: {stats['not_processed']}")
    md.append(f"- attachment_skipped: {stats['attachment_skipped']}")
    md.append("")
    
    error_docs = [d for d in docs if d.get("metadata", {}).get("fetch_status") == "error"]
    
    md.append("## 오류 레코드")
    md.append("")
    if error_docs:
        md.append("| id | url | error |")
        md.append("|---|---|---|")
        for d in error_docs[:20]:
            err_msg = d.get("metadata", {}).get("fetch_error", "").replace("|", "\\|")
            md.append(f"| {d['id']} | {d['url']} | {err_msg} |")
        if len(error_docs) > 20:
            md.append("")
            md.append(f"*외 {len(error_docs) - 20}개 오류 레코드 생략*")
    else:
        md.append("오류 레코드가 없습니다.")
        
    summary_dir = os.path.dirname(summary_path)
    if summary_dir and not os.path.exists(summary_dir):
        os.makedirs(summary_dir, exist_ok=True)
        
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

def main():
    parser = argparse.ArgumentParser(description="Enrich page documents in JSONL index by fetching raw text.")
    parser.add_argument("--input", required=True, help="Path to input JSONL document index")
    parser.add_argument("--output", required=True, help="Path to output enriched JSONL file")
    parser.add_argument("--max-chars", type=int, default=12000, help="Maximum characters to extract per page (default: 12000)")
    parser.add_argument("--limit", type=int, help="Limit number of pages to fetch")
    parser.add_argument("--dry-run", action="store_true", help="Print expected statistics without writing output file")
    parser.add_argument("--summary", help="Path to write Markdown summary report")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file does not exist: {args.input}", file=sys.stderr)
        sys.exit(1)
        
    docs = read_jsonl(args.input)
    
    enricher = DocumentEnricher()
    enriched_docs = enricher.enrich_records(docs, max_chars=args.max_chars, limit=args.limit)
    
    stats = {
        "total": len(enriched_docs),
        "fetched": 0,
        "skipped": 0,
        "error": 0,
        "not_processed": 0,
        "attachment_skipped": 0
    }
    
    for d in enriched_docs:
        status = d.get("metadata", {}).get("fetch_status")
        c_type = d.get("content_type", "")
        
        if status == "fetched":
            stats["fetched"] += 1
        elif status == "error":
            stats["error"] += 1
        elif status == "not_processed":
            stats["not_processed"] += 1
        elif status == "skipped":
            stats["skipped"] += 1
            if c_type == "attachment":
                stats["attachment_skipped"] += 1
                
    print(f"- 입력 파일 경로: {args.input}")
    print(f"- 출력 파일 경로: {args.output} (Dry-run: {args.dry_run})")
    print(f"- 전체 레코드 수: {stats['total']}")
    print(f"- fetched 수: {stats['fetched']}")
    print(f"- skipped 수: {stats['skipped']}")
    print(f"- error 수: {stats['error']}")
    print(f"- not_processed 수: {stats['not_processed']}")
    print(f"- attachment skipped 수: {stats['attachment_skipped']}")
    
    if not args.dry_run:
        write_jsonl(enriched_docs, args.output)
        
        if args.summary:
            generate_summary(enriched_docs, args.input, args.output, args.summary, stats)
            print(f"- summary 저장 경로: {args.summary}")
    else:
        if args.summary:
            print("- summary 저장 경로: (생략됨 - Dry-run 상태)")

if __name__ == "__main__":
    main()
