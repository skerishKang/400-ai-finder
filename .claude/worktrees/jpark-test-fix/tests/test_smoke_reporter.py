import os
import json
import pytest
from unittest.mock import MagicMock
from src.pipeline.smoke_reporter import SmokeTestRunner, make_safe_target_name
from src.pipeline.pipeline_runner import PipelineRunner

def test_safe_target_name():
    assert make_safe_target_name("example name") == "example-name"
    assert make_safe_target_name("example@name#123") == "examplename123"
    assert make_safe_target_name("example_name-123") == "example_name-123"
    assert make_safe_target_name("") == "target-001"
    assert make_safe_target_name(None) == "target-001"
    assert make_safe_target_name("@@@") == "target-001"

def test_single_target_success(tmp_path, monkeypatch):
    def mock_run(self, url, query):
        os.makedirs(self.output_dir, exist_ok=True)
        with open(os.path.join(self.output_dir, "homepage-map.json"), "w", encoding="utf-8") as f:
            json.dump({
                "sitemap": {"url_count": 10},
                "homepage": {
                    "navigation_links": [{"url": "a"} for _ in range(5)],
                    "attachment_links": [{"url": "b"} for _ in range(2)]
                }
            }, f)
        with open(os.path.join(self.output_dir, "document-index.jsonl"), "w", encoding="utf-8") as f:
            f.write("{}\n{}\n")
        with open(os.path.join(self.output_dir, "enriched-index.jsonl"), "w", encoding="utf-8") as f:
            f.write("{}\n")
        with open(os.path.join(self.output_dir, "search-results.json"), "w", encoding="utf-8") as f:
            json.dump({"result_count": 3}, f)
        with open(os.path.join(self.output_dir, "answer.json"), "w", encoding="utf-8") as f:
            json.dump({"ok": True, "answer_markdown": "Mock answer"}, f)
            
        return {
            "ok": True,
            "url": url,
            "query": query,
            "steps": [
                {"name": "homepage_map", "ok": True, "error": ""},
                {"name": "document_index", "ok": True, "error": ""},
                {"name": "enriched_index", "ok": True, "error": ""},
                {"name": "search", "ok": True, "error": ""},
                {"name": "answer", "ok": True, "error": ""}
            ]
        }
        
    monkeypatch.setattr(PipelineRunner, "run", mock_run)
    
    runner = SmokeTestRunner(output_dir=str(tmp_path), provider="mock")
    target = {"name": "Test target", "url": "https://example.com", "query": "test query"}
    
    report = runner.run_target(target)
    
    assert report["ok"] is True
    assert report["name"] == "Test target"
    assert report["metrics"]["sitemap_url_count"] == 10
    assert report["metrics"]["navigation_link_count"] == 5
    assert report["metrics"]["attachment_count"] == 2
    assert report["metrics"]["document_index_count"] == 2
    assert report["metrics"]["enriched_index_count"] == 1
    assert report["metrics"]["search_result_count"] == 3
    assert report["metrics"]["answer_ok"] is True
    assert len(report["warnings"]) == 0
    assert report["error"] == ""

def test_target_failure_does_not_stop_batch(tmp_path, monkeypatch):
    call_count = 0
    def mock_run(self, url, query):
        nonlocal call_count
        call_count += 1
        os.makedirs(self.output_dir, exist_ok=True)
        
        if call_count == 1:
            return {
                "ok": False,
                "error": "Failed step",
                "steps": [
                    {"name": "homepage_map", "ok": False, "error": "Failed step"}
                ]
            }
        else:
            with open(os.path.join(self.output_dir, "homepage-map.json"), "w", encoding="utf-8") as f:
                json.dump({"sitemap": {"url_count": 5}, "homepage": {"navigation_links": [], "attachment_links": []}}, f)
            with open(os.path.join(self.output_dir, "document-index.jsonl"), "w", encoding="utf-8") as f:
                f.write("{}\n")
            with open(os.path.join(self.output_dir, "enriched-index.jsonl"), "w", encoding="utf-8") as f:
                f.write("{}\n")
            with open(os.path.join(self.output_dir, "search-results.json"), "w", encoding="utf-8") as f:
                json.dump({"result_count": 1}, f)
            with open(os.path.join(self.output_dir, "answer.json"), "w", encoding="utf-8") as f:
                json.dump({"ok": True}, f)
                
            return {
                "ok": True,
                "steps": [
                    {"name": "homepage_map", "ok": True, "error": ""},
                    {"name": "document_index", "ok": True, "error": ""},
                    {"name": "enriched_index", "ok": True, "error": ""},
                    {"name": "search", "ok": True, "error": ""},
                    {"name": "answer", "ok": True, "error": ""}
                ]
            }
            
    monkeypatch.setattr(PipelineRunner, "run", mock_run)
    
    runner = SmokeTestRunner(output_dir=str(tmp_path), provider="mock")
    targets = [
        {"name": "failed-target", "url": "https://example.com/fail", "query": "fail"},
        {"name": "success-target", "url": "https://example.com/success", "query": "success"}
    ]
    
    batch_report = runner.run_targets(targets)
    
    assert batch_report["ok"] is False
    assert batch_report["target_count"] == 2
    assert batch_report["success_count"] == 1
    assert batch_report["failure_count"] == 1
    
    assert batch_report["targets"][0]["ok"] is False
    assert batch_report["targets"][0]["error"] == "Failed step"
    assert batch_report["targets"][1]["ok"] is True
    
    assert os.path.exists(os.path.join(tmp_path, "smoke-report.json"))
    assert os.path.exists(os.path.join(tmp_path, "smoke-report.md"))

def test_warnings_generation(tmp_path, monkeypatch):
    def mock_run(self, url, query):
        os.makedirs(self.output_dir, exist_ok=True)
        with open(os.path.join(self.output_dir, "homepage-map.json"), "w", encoding="utf-8") as f:
            json.dump({"sitemap": {"url_count": 0}, "homepage": {"navigation_links": [], "attachment_links": []}}, f)
        with open(os.path.join(self.output_dir, "document-index.jsonl"), "w", encoding="utf-8") as f:
            pass
        with open(os.path.join(self.output_dir, "enriched-index.jsonl"), "w", encoding="utf-8") as f:
            pass
        with open(os.path.join(self.output_dir, "search-results.json"), "w", encoding="utf-8") as f:
            json.dump({"result_count": 0}, f)
        with open(os.path.join(self.output_dir, "answer.json"), "w", encoding="utf-8") as f:
            json.dump({"ok": False}, f)
            
        return {
            "ok": True,
            "steps": [
                {"name": "homepage_map", "ok": True, "error": ""},
                {"name": "document_index", "ok": True, "error": ""},
                {"name": "enriched_index", "ok": True, "error": ""},
                {"name": "search", "ok": True, "error": ""},
                {"name": "answer", "ok": True, "error": ""}
            ]
        }
        
    monkeypatch.setattr(PipelineRunner, "run", mock_run)
    runner = SmokeTestRunner(output_dir=str(tmp_path), provider="mock")
    report = runner.run_target({"name": "warn-target", "url": "https://example.com", "query": "warn"})
    
    assert "no sitemap urls found" in report["warnings"]
    assert "no navigation links found" in report["warnings"]
    assert "empty document index" in report["warnings"]
    assert "empty enriched index" in report["warnings"]
    assert "no search results" in report["warnings"]
    assert "answer generation failed" in report["warnings"]
    
def test_markdown_report_generation():
    runner = SmokeTestRunner(output_dir="dummy", provider="mock")
    report = {
        "ok": False,
        "target_count": 2,
        "success_count": 1,
        "failure_count": 1,
        "output_dir": "dummy_runs",
        "targets": [
            {
                "name": "target1",
                "url": "https://example.com/1",
                "query": "query1",
                "ok": True,
                "output_dir": "dummy_runs/target1",
                "pipeline_result_path": "dummy_runs/target1/pipeline-result.json",
                "answer_path": "dummy_runs/target1/answer.json",
                "answer_markdown_path": "dummy_runs/target1/answer.md",
                "metrics": {
                    "sitemap_url_count": 10,
                    "navigation_link_count": 5,
                    "attachment_count": 1,
                    "document_index_count": 2,
                    "enriched_index_count": 2,
                    "search_result_count": 3
                },
                "warnings": [],
                "error": ""
            },
            {
                "name": "target2",
                "url": "https://example.com/2",
                "query": "query2",
                "ok": False,
                "output_dir": "dummy_runs/target2",
                "pipeline_result_path": "dummy_runs/target2/pipeline-result.json",
                "answer_path": "dummy_runs/target2/answer.json",
                "answer_markdown_path": "dummy_runs/target2/answer.md",
                "metrics": {
                    "sitemap_url_count": 0,
                    "navigation_link_count": 0,
                    "attachment_count": 0,
                    "document_index_count": 0,
                    "enriched_index_count": 0,
                    "search_result_count": 0
                },
                "warnings": ["no sitemap urls found", "pipeline failed"],
                "error": "Failed step"
            }
        ]
    }
    
    md_content = runner.generate_markdown_summary(report)
    assert "# AI파인더 Smoke Test Report" in md_content
    assert "| target1 | true | 10 | 5 | 2 | 2 | 3 | none |" in md_content
    assert "| target2 | false | 0 | 0 | 0 | 0 | 0 | no sitemap urls found, pipeline failed |" in md_content
    assert "### target2" in md_content
    assert "- Error: Failed step" in md_content

def test_config_parsing(tmp_path):
    config_file = tmp_path / "targets.json"
    config_data = {
        "targets": [
            {"name": "test-1", "url": "https://example.com/1", "query": "q1"},
            {"name": "test-2", "url": "https://example.com/2", "query": "q2"}
        ]
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    with open(config_file, "r", encoding="utf-8") as f:
        parsed_data = json.load(f)
        
    assert len(parsed_data["targets"]) == 2
    assert parsed_data["targets"][0]["name"] == "test-1"


def test_smoke_runner_fetch_provider_default():
    """SmokeTestRunner fetch_provider defaults to None."""
    runner = SmokeTestRunner(output_dir="/tmp/smoke-test", provider="mock")
    assert runner.fetch_provider is None


def test_smoke_runner_fetch_provider_set():
    """SmokeTestRunner accepts fetch_provider param and passes to PipelineRunner."""
    runner = SmokeTestRunner(
        output_dir="/tmp/smoke-test",
        provider="mock",
        fetch_provider="requests",
    )
    assert runner.fetch_provider == "requests"
