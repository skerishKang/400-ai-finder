import os
import sys
import json
import argparse
from collections import Counter

# Add the project root directory to the python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.indexer.document_indexer import DocumentIndexer

def write_jsonl(docs, filepath):
    output_dir = os.path.dirname(filepath)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        
    with open(filepath, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

def generate_summary_md(docs, input_path, summary_path):
    total_count = len(docs)
    page_count = sum(1 for d in docs if d["content_type"] == "page")
    attachment_count = sum(1 for d in docs if d["content_type"] == "attachment")
    category_counts = Counter(d["category"] for d in docs)
    
    md = []
    md.append("# 문서 인덱스 요약")
    md.append("")
    md.append("## 입력")
    md.append("")
    md.append(f"- Homepage map: {input_path}")
    md.append("")
    md.append("## 통계")
    md.append("")
    md.append(f"- 전체 레코드 수: {total_count}")
    md.append(f"- page: {page_count}")
    md.append(f"- attachment: {attachment_count}")
    md.append("")
    md.append("## 카테고리 분포")
    md.append("")
    md.append("| category | count |")
    md.append("|---|---:|")
    for cat in sorted(category_counts.keys()):
        md.append(f"| {cat} | {category_counts[cat]} |")
    md.append("")
    
    md.append("## 샘플 레코드")
    md.append("")
    if docs:
        md.append("| ID | Title | Content Type | Category | URL |")
        md.append("|---|---|---|---|---|")
        for d in docs[:20]:
            title_escaped = d["title"].replace("|", "\\|")
            md.append(f"| {d['id']} | {title_escaped} | {d['content_type']} | {d['category']} | {d['canonical_url']} |")
        if len(docs) > 20:
            md.append("")
            md.append(f"*외 {len(docs) - 20}개 레코드 생략*")
    else:
        md.append("레코드가 없습니다.")
        
    summary_dir = os.path.dirname(summary_path)
    if summary_dir and not os.path.exists(summary_dir):
        os.makedirs(summary_dir, exist_ok=True)
        
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

def main():
    parser = argparse.ArgumentParser(description="Build a search-friendly document index from homepage map.")
    parser.add_argument("--input", required=True, help="Path to the input homepage map JSON file")
    parser.add_argument("--output", required=True, help="Path to the output JSONL file")
    parser.add_argument("--summary", help="Path to the output summary Markdown file")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file does not exist: {args.input}", file=sys.stderr)
        sys.exit(1)
        
    with open(args.input, "r", encoding="utf-8") as f:
        homepage_map = json.load(f)
        
    indexer = DocumentIndexer()
    docs = indexer.build_index(homepage_map)
    
    write_jsonl(docs, args.output)
    
    total_count = len(docs)
    page_count = sum(1 for d in docs if d["content_type"] == "page")
    attachment_count = sum(1 for d in docs if d["content_type"] == "attachment")
    category_counts = Counter(d["category"] for d in docs)
    
    # CLI outputs
    print(f"- 읽은 homepage map 파일 경로: {args.input}")
    print(f"- 생성한 문서 레코드 수: {total_count}")
    print("- category별 개수:")
    for cat in sorted(category_counts.keys()):
        print(f"  - {cat}: {category_counts[cat]}")
    print("- content_type별 개수:")
    print(f"  - page: {page_count}")
    print(f"  - attachment: {attachment_count}")
    print(f"- output 저장 경로: {args.output}")
    
    if args.summary:
        generate_summary_md(docs, args.input, args.summary)
        print(f"- summary 저장 경로: {args.summary}")

if __name__ == "__main__":
    main()
