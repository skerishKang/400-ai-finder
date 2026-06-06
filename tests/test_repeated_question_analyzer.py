"""Tests for the repeated-question analyzer boundary (Stage 352)."""

from __future__ import annotations

import ast
from pathlib import Path
import pytest

from src.analytics.repeated_question_analyzer import (
    analyze_repeated_questions,
    PromotionCandidate,
)


def test_analyzer_groups_repeated_normalized_questions():
    """Assert analyzer groups questions by their normalized key."""
    events = [
        {"raw_question": "민원 신청 어디서 해?", "normalized_question": "민원 신청 어디서 해"},
        {"raw_question": "민원신청 어디서해?", "normalized_question": "민원 신청 어디서 해"},
        {"raw_question": "민원 신청 어디서 해", "normalized_question": "민원 신청 어디서 해"},
    ]
    candidates = analyze_repeated_questions(events, min_count=3)
    assert len(candidates) == 1
    assert candidates[0].normalized_key == "민원 신청 어디서 해"
    assert candidates[0].count == 3


def test_analyzer_emits_cache_candidate_for_repeated_successful_question():
    """Assert candidate with high successful repeats is classified as review_for_cache."""
    events = [
        {
            "raw_question": "구청장이 누구야?",
            "normalized_question": "구청장 누구야",
            "answer_status": "success",
            "fallback_used": False,
            "guard_status": "pass",
            "source_domains": ["bukgu.gwangju.kr"],
        }
    ] * 5  # count = 5
    
    candidates = analyze_repeated_questions(events, min_count=3)
    assert len(candidates) == 1
    assert candidates[0].recommended_action == "review_for_cache"
    assert candidates[0].confidence == "high"


def test_analyzer_marks_repeated_no_results_as_retrieval_gap_not_promotion():
    """Assert that repeated failed or no-results queries are marked as retrieval_gap."""
    events = [
        {
            "raw_question": "이상한 질문?",
            "normalized_question": "이상한 질문",
            "answer_status": "no_results",
            "guard_status": "no_results",
            "source_domains": [],
        }
    ] * 3
    
    candidates = analyze_repeated_questions(events, min_count=3)
    assert len(candidates) == 1
    assert candidates[0].recommended_action == "retrieval_gap"
    assert "NO_RESULTS" in candidates[0].reason


def test_analyzer_respects_min_count():
    """Assert groups with counts below min_count are ignored."""
    events = [
        {"raw_question": "질문 1", "normalized_question": "질문 1"},
        {"raw_question": "질문 1", "normalized_question": "질문 1"},
        {"raw_question": "질문 2", "normalized_question": "질문 2"},
    ]
    candidates = analyze_repeated_questions(events, min_count=3)
    assert len(candidates) == 0


def test_analyzer_deduplicates_source_domains():
    """Assert source domains in candidate outputs are deduplicated."""
    events = [
        {
            "raw_question": "민원 신청",
            "normalized_question": "민원 신청",
            "source_domains": ["bukgu.gwangju.kr", "eminwon.bukgu.gwangju.kr"],
        },
        {
            "raw_question": "민원 신청",
            "normalized_question": "민원 신청",
            "source_domains": ["bukgu.gwangju.kr"],
        },
        {
            "raw_question": "민원 신청",
            "normalized_question": "민원 신청",
            "source_domains": ["eminwon.bukgu.gwangju.kr"],
        },
    ]
    candidates = analyze_repeated_questions(events, min_count=3)
    assert len(candidates) == 1
    assert candidates[0].source_domains == ("bukgu.gwangju.kr", "eminwon.bukgu.gwangju.kr")


def test_analyzer_redacts_secret_like_values_from_candidate_output():
    """Assert any secret-like raw questions or domains are redacted from output."""
    events = [
        {
            "raw_question": "My key is sk-SuperSecretOpenAIKeyGoesHere",
            "normalized_question": "my key is super secret",
            "source_domains": ["http://invalid-secret-key-api_key:secretval@test.com/path"],
        }
    ] * 3
    
    candidates = analyze_repeated_questions(events, min_count=3)
    assert len(candidates) == 1
    cand = candidates[0]
    
    # Candidate outputs must be redacted
    assert "sk-SuperSecret" not in cand.representative_question
    assert "secretval" not in "".join(cand.source_domains)
    assert "[REDACTED]" in cand.representative_question


def test_analyzer_does_not_write_scenario_or_snapshot_files(tmp_path):
    """Assert that running the analyzer does not write or generate any files in the workspace."""
    # We record current state of workspace or watch files
    events = [
        {
            "raw_question": "구청장이 누구야?",
            "normalized_question": "구청장 누구야",
            "answer_status": "success",
            "fallback_used": False,
            "guard_status": "pass",
            "source_domains": ["bukgu.gwangju.kr"],
        }
    ] * 4
    
    # Let's count files before in current dir
    files_before = set(Path("configs").rglob("*")) if Path("configs").exists() else set()
    
    # Run analyzer
    candidates = analyze_repeated_questions(events, min_count=3)
    assert len(candidates) == 1
    
    files_after = set(Path("configs").rglob("*")) if Path("configs").exists() else set()
    
    # Verify no new files created in configs
    assert files_before == files_after


def test_analyzer_imports_no_provider_or_network_modules():
    """Verify that repeated_question_analyzer.py is pure and imports no network/LLM modules."""
    analyzer_path = Path(__file__).parent.parent / "src" / "analytics" / "repeated_question_analyzer.py"
    with open(analyzer_path, "r", encoding="utf-8") as f:
        source = f.read()
        
    tree = ast.parse(source)
    banned_prefixes = ("src.llm", "src.fetch", "firecrawl", "requests", "httpx", "urllib3")
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(banned_prefixes):
                    pytest.fail(f"repeated_question_analyzer should not import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(banned_prefixes):
                pytest.fail(f"repeated_question_analyzer should not import from: {node.module}")
