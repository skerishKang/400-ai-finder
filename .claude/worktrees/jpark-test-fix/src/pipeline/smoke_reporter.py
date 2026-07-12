import os
import re
import json
from datetime import datetime
from typing import Any
from .pipeline_runner import PipelineRunner

def make_safe_target_name(name: str, fallback_idx: int = 1) -> str:
    if not name:
        return f"target-{fallback_idx:03d}"
    # Replace spaces with hyphens
    s = name.strip().replace(" ", "-")
    # Remove any non-alphanumeric, non-hyphen, non-underscore characters
    s = re.sub(r"[^a-zA-Z0-9\-_]", "", s)
    if not s:
        return f"target-{fallback_idx:03d}"
    return s

class SmokeTestRunner:
    def __init__(
        self,
        output_dir: str,
        provider: str = "mock",
        fetch_provider: str | None = None,
        top_k: int = 5,
        max_sources: int = 5,
        max_enrich_pages: int = 10,
        max_sitemap_urls: int = 200,
        max_sitemaps: int = 10,
        max_chars: int = 12000
    ):
        self.output_dir = output_dir
        self.provider = provider
        self.fetch_provider = fetch_provider  # None = original behavior
        self.top_k = top_k
        self.max_sources = max_sources
        self.max_enrich_pages = max_enrich_pages
        self.max_sitemap_urls = max_sitemap_urls
        self.max_sitemaps = max_sitemaps
        self.max_chars = max_chars

    def run_target(self, target: dict, index: int = 1) -> dict:
        name = target.get("name", "")
        url = target.get("url", "")
        query = target.get("query", "")
        
        safe_name = make_safe_target_name(name, index)
        target_output_dir = os.path.join(self.output_dir, safe_name)
        
        runner = PipelineRunner(
            output_dir=target_output_dir,
            provider=self.provider,
            fetch_provider=self.fetch_provider,
            top_k=self.top_k,
            max_sources=self.max_sources,
            max_enrich_pages=self.max_enrich_pages,
            max_sitemap_urls=self.max_sitemap_urls,
            max_sitemaps=self.max_sitemaps,
            max_chars=self.max_chars
        )
        
        pipeline_res = {}
        error_msg = ""
        try:
            pipeline_res = runner.run(url=url, query=query)
        except Exception as e:
            error_msg = str(e)
            pipeline_res = {"ok": False, "error": error_msg, "steps": []}
            
        ok = pipeline_res.get("ok", False)
        
        # Paths
        homepage_map_path = os.path.join(target_output_dir, "homepage-map.json")
        document_index_path = os.path.join(target_output_dir, "document-index.jsonl")
        enriched_index_path = os.path.join(target_output_dir, "enriched-index.jsonl")
        search_results_path = os.path.join(target_output_dir, "search-results.json")
        answer_path = os.path.join(target_output_dir, "answer.json")
        answer_markdown_path = os.path.join(target_output_dir, "answer.md")
        pipeline_result_path = os.path.join(target_output_dir, "pipeline-result.json")
        
        sitemap_url_count = 0
        navigation_link_count = 0
        attachment_count = 0
        document_index_count = 0
        enriched_index_count = 0
        search_result_count = 0
        answer_ok = False
        
        # Parse metrics from files
        if os.path.exists(homepage_map_path):
            try:
                with open(homepage_map_path, "r", encoding="utf-8") as f:
                    h_map = json.load(f)
                    sitemap_sec = h_map.get("sitemap", {})
                    sitemap_url_count = sitemap_sec.get("url_count", len(sitemap_sec.get("urls", [])))
                    homepage_sec = h_map.get("homepage", {})
                    navigation_link_count = len(homepage_sec.get("navigation_links", []))
                    attachment_count = len(homepage_sec.get("attachment_links", []))
            except Exception:
                pass
                
        if os.path.exists(document_index_path):
            try:
                with open(document_index_path, "r", encoding="utf-8") as f:
                    document_index_count = sum(1 for line in f if line.strip())
            except Exception:
                pass
                
        if os.path.exists(enriched_index_path):
            try:
                with open(enriched_index_path, "r", encoding="utf-8") as f:
                    enriched_index_count = sum(1 for line in f if line.strip())
            except Exception:
                pass
                
        if os.path.exists(search_results_path):
            try:
                with open(search_results_path, "r", encoding="utf-8") as f:
                    s_res = json.load(f)
                    search_result_count = s_res.get("result_count", len(s_res.get("results", [])))
            except Exception:
                pass
                
        if os.path.exists(answer_path):
            try:
                with open(answer_path, "r", encoding="utf-8") as f:
                    answer_data = json.load(f)
                    answer_ok = answer_data.get("ok", False)
            except Exception:
                pass

        # Warnings rules
        warnings = []
        if sitemap_url_count == 0:
            warnings.append("no sitemap urls found")
        if navigation_link_count == 0:
            warnings.append("no navigation links found")
        if document_index_count == 0:
            warnings.append("empty document index")
        if enriched_index_count == 0:
            warnings.append("empty enriched index")
        if search_result_count == 0:
            warnings.append("no search results")
        if not answer_ok:
            warnings.append("answer generation failed")
        if not ok:
            warnings.append("pipeline failed")
            
        required_steps = ["homepage_map", "document_index", "enriched_index", "search", "answer"]
        steps_map = {s["name"]: s for s in pipeline_res.get("steps", [])}
        steps_info = []
        for step_name in required_steps:
            if step_name in steps_map:
                steps_info.append({
                    "name": step_name,
                    "ok": steps_map[step_name]["ok"],
                    "error": steps_map[step_name]["error"]
                })
            else:
                steps_info.append({
                    "name": step_name,
                    "ok": False,
                    "error": "Not executed"
                })
                
        target_report = {
            "name": name,
            "url": url,
            "query": query,
            "ok": ok,
            "output_dir": target_output_dir,
            "pipeline_result_path": pipeline_result_path,
            "answer_path": answer_path,
            "answer_markdown_path": answer_markdown_path,
            "metrics": {
                "sitemap_url_count": sitemap_url_count,
                "navigation_link_count": navigation_link_count,
                "attachment_count": attachment_count,
                "document_index_count": document_index_count,
                "enriched_index_count": enriched_index_count,
                "search_result_count": search_result_count,
                "answer_ok": answer_ok
            },
            "steps": steps_info,
            "warnings": warnings,
            "error": error_msg or pipeline_res.get("error", "")
        }
        
        return target_report

    def run_targets(self, targets: list[dict]) -> dict:
        os.makedirs(self.output_dir, exist_ok=True)
        
        results = []
        success_count = 0
        failure_count = 0
        
        for idx, target in enumerate(targets, start=1):
            try:
                target_report = self.run_target(target, idx)
            except Exception as e:
                target_report = {
                    "name": target.get("name", ""),
                    "url": target.get("url", ""),
                    "query": target.get("query", ""),
                    "ok": False,
                    "output_dir": os.path.join(self.output_dir, make_safe_target_name(target.get("name", ""), idx)),
                    "pipeline_result_path": "",
                    "answer_path": "",
                    "answer_markdown_path": "",
                    "metrics": {
                        "sitemap_url_count": 0,
                        "navigation_link_count": 0,
                        "attachment_count": 0,
                        "document_index_count": 0,
                        "enriched_index_count": 0,
                        "search_result_count": 0,
                        "answer_ok": False
                    },
                    "steps": [],
                    "warnings": ["pipeline failed"],
                    "error": str(e)
                }
                
            if target_report["ok"]:
                success_count += 1
            else:
                failure_count += 1
                
            results.append(target_report)
            
        overall_ok = (failure_count == 0 and len(targets) > 0)
        
        overall_warnings = []
        if failure_count > 0:
            overall_warnings.append(f"{failure_count} target(s) failed")
            
        batch_report = {
            "ok": overall_ok,
            "target_count": len(targets),
            "success_count": success_count,
            "failure_count": failure_count,
            "output_dir": self.output_dir,
            "targets": results,
            "warnings": overall_warnings,
            "error": "" if overall_ok else f"{failure_count} target(s) failed"
        }
        
        # Save JSON report
        report_json_path = os.path.join(self.output_dir, "smoke-report.json")
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(batch_report, f, ensure_ascii=False, indent=2)
            
        # Save Markdown report
        report_md_path = os.path.join(self.output_dir, "smoke-report.md")
        md_content = self.generate_markdown_summary(batch_report)
        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
            
        return batch_report

    def generate_markdown_summary(self, report: dict) -> str:
        md = []
        md.append("# AI파인더 Smoke Test Report")
        md.append("")
        md.append("## Summary")
        md.append("")
        md.append(f"- Target count: {report['target_count']}")
        md.append(f"- Success: {report['success_count']}")
        md.append(f"- Failure: {report['failure_count']}")
        md.append(f"- Output dir: {report['output_dir']}")
        md.append("")
        
        md.append("## Targets")
        md.append("")
        md.append("| name | ok | sitemap urls | nav links | docs | enriched | search results | warnings |")
        md.append("|---|---:|---:|---:|---:|---:|---:|---|")
        
        for t in report["targets"]:
            m = t["metrics"]
            warn_str = ", ".join(t["warnings"]) if t["warnings"] else "none"
            ok_str = "true" if t["ok"] else "false"
            md.append(
                f"| {t['name']} | {ok_str} | {m['sitemap_url_count']} | "
                f"{m['navigation_link_count']} | {m['document_index_count']} | "
                f"{m['enriched_index_count']} | {m['search_result_count']} | {warn_str} |"
            )
        md.append("")
        
        md.append("## Details")
        md.append("")
        for t in report["targets"]:
            md.append(f"### {t['name']}")
            md.append("")
            md.append(f"- URL: {t['url']}")
            md.append(f"- Query: {t['query']}")
            md.append(f"- Output: {t['output_dir']}")
            md.append(f"- Pipeline result: {t['pipeline_result_path']}")
            md.append(f"- Answer: {t['answer_path']}")
            warn_str = ", ".join(t["warnings"]) if t["warnings"] else "none"
            md.append(f"- Warnings: {warn_str}")
            err_str = t["error"] if t["error"] else "none"
            md.append(f"- Error: {err_str}")
            md.append("")
            
        return "\n".join(md)
