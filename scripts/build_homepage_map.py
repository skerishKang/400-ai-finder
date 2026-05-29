import os
import sys
import json
import argparse

# Add the project root directory to the python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.crawler.homepage_mapper import HomepageMapper

def generate_markdown(data):
    md = []
    md.append(f"# 홈페이지 지도 요약 ({data['start_url']})")
    md.append("")
    md.append("## 통계 정보")
    md.append(f"- **사이트맵 내 URL 수**: {data['stats']['sitemap_url_count']}개")
    md.append(f"- **네비게이션 메뉴 링크 수**: {data['stats']['navigation_link_count']}개")
    md.append(f"- **첨부파일 링크 수**: {data['stats']['attachment_count']}개")
    md.append("")
    
    md.append("## 카테고리별 URL 분포")
    md.append("| 카테고리 | 개수 |")
    md.append("| --- | --- |")
    for cat, count in data['stats']['category_counts'].items():
        md.append(f"| {cat} | {count} |")
    md.append("")
    
    md.append("## 네비게이션 메뉴 (Navigation Links)")
    if data['homepage']['navigation_links']:
        for link in data['homepage']['navigation_links']:
            md.append(f"- [{link['text']}]({link['url']}) (카테고리: `{link['category']}`)")
    else:
        md.append("- 발견된 메뉴 링크가 없습니다.")
    md.append("")
    
    md.append("## 첨부파일 메뉴 (Attachment Links)")
    if data['homepage']['attachment_links']:
        for link in data['homepage']['attachment_links']:
            md.append(f"- [{link['text']}]({link['url']}) (형식: `{link['type']}`)")
    else:
        md.append("- 발견된 첨부파일 링크가 없습니다.")
    md.append("")

    md.append("## 사이트맵 URL 일부 (최대 50개)")
    if data['sitemap']['urls']:
        for item in data['sitemap']['urls'][:50]:
            lastmod_str = f", lastmod: {item['lastmod']}" if item['lastmod'] else ""
            md.append(f"- {item['url']} (카테고리: `{item['category']}`{lastmod_str})")
        if len(data['sitemap']['urls']) > 50:
            md.append(f"- ...외 {len(data['sitemap']['urls']) - 50}개 URL 생략")
    else:
        md.append("- 사이트맵에서 추출된 URL이 없습니다.")
    
    return "\n".join(md)

def main():
    parser = argparse.ArgumentParser(description="Generate a homepage map using sitemaps and menu links.")
    parser.add_argument("--url", required=True, help="The start URL to map")
    parser.add_argument("--output", help="Output path to save the JSON result")
    parser.add_argument("--markdown", help="Output path to save the Markdown summary")
    parser.add_argument("--max-sitemaps", type=int, default=10, help="Maximum number of sitemaps to parse (default: 10)")
    parser.add_argument("--max-sitemap-urls", type=int, default=500, help="Maximum sitemap URLs to save (default: 500)")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds (default: 15)")
    
    args = parser.parse_args()
    
    mapper = HomepageMapper(
        timeout=args.timeout,
        max_sitemaps=args.max_sitemaps,
        max_sitemap_urls=args.max_sitemap_urls
    )
    
    result = mapper.build_map(args.url)
    
    json_result = json.dumps(result, ensure_ascii=False, indent=2)
    
    if args.output:
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_result)
        print(f"JSON results saved to {args.output}")
    else:
        print(json_result)
        
    if args.markdown:
        md_result = generate_markdown(result)
        markdown_dir = os.path.dirname(args.markdown)
        if markdown_dir and not os.path.exists(markdown_dir):
            os.makedirs(markdown_dir, exist_ok=True)
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(md_result)
        print(f"Markdown summary saved to {args.markdown}")

if __name__ == "__main__":
    main()
