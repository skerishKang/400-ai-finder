"""Deterministic fake adapter for the single-scenario live smoke path.

This module is intentionally offline. It does not call live providers, fetch
providers, external networks, Firecrawl, or the app pipeline. It only turns one
validated smoke scenario into the Stage 62-compatible result payload shape used
by the Stage 65 dry runner.
"""

from __future__ import annotations

from typing import Any

FAKE_SINGLE_LIVE_ADAPTER_NAME = "fake-single-scenario-live-adapter"
OFFLINE_DRY_RUN_PROVIDER_LABEL = "offline-dry-run"


def answer_keyword_from_scenario(scenario: dict[str, Any]) -> str:
    """Return the deterministic answer keyword used by the fake adapter."""
    criteria = scenario.get("pass_criteria", {})
    answer_contains_any = criteria.get("answer_contains_any")
    if isinstance(answer_contains_any, list):
        for keyword in answer_contains_any:
            if isinstance(keyword, str) and keyword.strip():
                return keyword.strip()

    expected_keywords = scenario.get("expected_keywords")
    if isinstance(expected_keywords, list):
        for keyword in expected_keywords:
            if isinstance(keyword, str) and keyword.strip():
                return keyword.strip()

    question = scenario.get("question")
    return question if isinstance(question, str) and question.strip() else "정보"


def source_title_from_scenario(scenario: dict[str, Any], keyword: str) -> str:
    """Return a deterministic fake source title for a scenario."""
    category = scenario.get("category")
    if isinstance(category, str) and category.strip():
        return f"{keyword} {category}"
    return keyword


def build_fake_single_live_result_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    """Build one Stage 62-compatible payload without any live execution."""
    scenario_id = str(scenario["id"])
    site_id = str(scenario["site_id"])
    question = str(scenario["question"])
    expected_domain = str(scenario["expected_domain"])
    criteria = scenario.get("pass_criteria", {})
    min_sources = criteria.get("min_sources") if isinstance(criteria, dict) else None
    keyword = answer_keyword_from_scenario(scenario)

    needs_source = isinstance(min_sources, int) and min_sources > 0
    if needs_source:
        sources = [
            {
                "title": source_title_from_scenario(scenario, keyword),
                "url": f"https://{expected_domain}/stage65-dry/{scenario_id}",
            }
        ]
        return {
            "scenario_id": scenario_id,
            "site_id": site_id,
            "query": question,
            "status": "answered",
            "answer": f"{keyword} 관련 정보는 {site_id} 홈페이지의 Stage 65 dry-run 출처에서 확인할 수 있습니다.",
            "sources": sources,
            "fallback_used": False,
            "ok": True,
            "answer_ok": True,
        }

    return {
        "scenario_id": scenario_id,
        "site_id": site_id,
        "query": question,
        "status": "fallback",
        "answer": f"{keyword} 관련 정보는 출처가 부족하므로 홈페이지에서 직접 확인해 주세요.",
        "sources": [],
        "fallback_used": True,
        "ok": True,
        "answer_ok": True,
    }
