"""Tests for the LLM-first positive site-search router.

The router is decoupled from PipelineRunner so tests inject a mock
LLM provider and assert on the decision alone. No live API calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.llm.site_search_router import (
    RouterDecision,
    SiteSearchRouter,
    clarify_fallback_direct_answer,
    default_fallback_decision,
    greeting_fallback_direct_answer,
)


class MockProvider:
    """Minimal mock of the LLM provider interface used by the router.

    The router only needs ``.generate(prompt=..., model=...)`` to return
    an object with a ``text`` attribute. No network calls.
    """

    def __init__(self, text: str = "", raise_exc: bool = False) -> None:
        self.text = text
        self.raise_exc = raise_exc
        self.last_prompt: str | None = None
        self.last_model: str | None = None

    def generate(self, prompt: str, model: str = "") -> Any:
        self.last_prompt = prompt
        self.last_model = model
        if self.raise_exc:
            raise RuntimeError("mock provider failure")
        return SimpleNamespace(text=self.text)


SITE_NAME = "광주광역시 북구청"


# ----------------------------------------------------------------------
# Fallback helpers
# ----------------------------------------------------------------------


def test_default_fallback_decision_is_site_search_positive():
    d = default_fallback_decision("민원서식 어디서 받아?", SITE_NAME)
    assert d.route == "site_search"
    assert d.should_search_site is True
    assert d.confidence == 0.0
    assert d.reason == "router_fallback_positive"
    assert d.search_query == "민원서식 어디서 받아?"
    assert d.direct_answer == ""


def test_default_fallback_decision_handles_empty_question():
    d = default_fallback_decision("", SITE_NAME)
    assert d.route == "site_search"
    assert d.search_query  # falls back to site name based hint


def test_greeting_fallback_mentions_site():
    msg = greeting_fallback_direct_answer(SITE_NAME)
    assert SITE_NAME in msg
    assert "민원" in msg and "공고" in msg


def test_greeting_fallback_handles_blank_site_name():
    msg = greeting_fallback_direct_answer("")
    assert "해당 기관" in msg


def test_clarify_fallback_mentions_site():
    msg = clarify_fallback_direct_answer(SITE_NAME)
    assert SITE_NAME in msg


# ----------------------------------------------------------------------
# JSON parsing
# ----------------------------------------------------------------------


def test_parse_valid_decision():
    payload = (
        '{"route": "site_search", "should_search_site": true, '
        '"confidence": 0.84, "reason": "민원 관련", '
        '"search_query": "민원서식", "direct_answer": ""}'
    )
    router = SiteSearchRouter(provider=MockProvider(payload), site_name=SITE_NAME)
    d = router.decide("민원서식 어디서 받아?")
    assert d.route == "site_search"
    assert d.should_search_site is True
    assert d.confidence == 0.84
    assert d.reason == "민원 관련"
    assert d.search_query == "민원서식"


def test_parse_valid_decision_with_surrounding_text():
    payload = (
        "Here is my answer:\n"
        '{"route": "direct_answer", "should_search_site": false, '
        '"confidence": 0.95, "reason": "명백한 인사", '
        '"search_query": "", "direct_answer": "안녕하세요"}\n'
        "Done."
    )
    router = SiteSearchRouter(provider=MockProvider(payload), site_name=SITE_NAME)
    d = router.decide("안녕")
    assert d.route == "direct_answer"
    assert d.should_search_site is False
    assert d.direct_answer == "안녕하세요"


def test_parse_decision_normalizes_should_search_site():
    # site_search should always set should_search_site=True
    payload = (
        '{"route": "site_search", "should_search_site": false, '
        '"confidence": 0.5, "reason": "x", '
        '"search_query": "", "direct_answer": ""}'
    )
    router = SiteSearchRouter(provider=MockProvider(payload), site_name=SITE_NAME)
    d = router.decide("복지 지원사업은?")
    assert d.route == "site_search"
    assert d.should_search_site is True
    # When LLM does not supply search_query, falls back to the user question
    assert d.search_query == "복지 지원사업은?"


def test_parse_decision_unknown_route_falls_back():
    payload = '{"route": "smoke_signal", "should_search_site": true}'
    router = SiteSearchRouter(provider=MockProvider(payload), site_name=SITE_NAME)
    d = router.decide("어떻게 찾아?")
    # Unparseable route → positive site_search fallback
    assert d.route == "site_search"
    assert d.reason == "router_fallback_positive"


def test_parse_decision_garbage_falls_back():
    router = SiteSearchRouter(provider=MockProvider("not json at all"), site_name=SITE_NAME)
    d = router.decide("민원서식?")
    assert d.route == "site_search"
    assert d.reason == "router_fallback_positive"


def test_parse_decision_empty_text_falls_back():
    router = SiteSearchRouter(provider=MockProvider(""), site_name=SITE_NAME)
    d = router.decide("민원서식?")
    assert d.route == "site_search"
    assert d.reason == "router_fallback_positive"


def test_provider_exception_falls_back_to_site_search():
    router = SiteSearchRouter(
        provider=MockProvider(raise_exc=True), site_name=SITE_NAME
    )
    d = router.decide("고시공고 어디서 봐?")
    assert d.route == "site_search"
    assert d.search_query == "고시공고 어디서 봐?"


def test_no_provider_falls_back_to_site_search():
    router = SiteSearchRouter(provider=None, site_name=SITE_NAME)
    d = router.decide("민원서식?")
    assert d.route == "site_search"
    assert d.reason == "router_fallback_positive"


def test_confidence_is_clamped_into_unit_interval():
    payload = (
        '{"route": "site_search", "should_search_site": true, '
        '"confidence": 5.0, "reason": "x", '
        '"search_query": "y", "direct_answer": ""}'
    )
    router = SiteSearchRouter(provider=MockProvider(payload), site_name=SITE_NAME)
    d = router.decide("질문")
    assert 0.0 <= d.confidence <= 1.0


def test_direct_answer_clarify_disable_search_site():
    payload = (
        '{"route": "clarify", "should_search_site": true, '
        '"confidence": 0.4, "reason": "너무 짧음", '
        '"search_query": "", "direct_answer": "조금만 알려주세요"}'
    )
    router = SiteSearchRouter(provider=MockProvider(payload), site_name=SITE_NAME)
    d = router.decide("신청은?")
    assert d.route == "clarify"
    assert d.should_search_site is False
    assert d.direct_answer == "조금만 알려주세요"


def test_router_sends_prompt_in_decide():
    payload = '{"route": "site_search"}'
    provider = MockProvider(payload)
    router = SiteSearchRouter(provider=provider, site_name=SITE_NAME)
    router.decide("민원서식 어디서 받아?")
    assert provider.last_prompt is not None
    assert SITE_NAME in provider.last_prompt
    assert "민원서식 어디서 받아?" in provider.last_prompt


# ----------------------------------------------------------------------
# SiteDemoRunner integration with router
# ----------------------------------------------------------------------


def test_runner_uses_direct_answer_route_skips_pipeline(tmp_path):
    """When the router returns direct_answer, the runner should not
    invoke the pipeline and should return a greeting/intro answer.
    """
    from src.demo.site_demo_runner import SiteDemoRunner

    payload = (
        '{"route": "direct_answer", "should_search_site": false, '
        '"confidence": 0.9, "reason": "명백한 인사", '
        '"search_query": "", "direct_answer": "안녕하세요"}'
    )
    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="mock",
        output_dir=str(tmp_path),
    )
    runner.router = SiteSearchRouter(provider=MockProvider(payload), site_name=runner.profile.name)
    result = runner.answer("안녕")
    assert result["route"] == "direct_answer"
    assert result["should_search_site"] is False
    assert result["answer_mode"] == "direct_answer"
    assert result["sources"] == []
    # The router-supplied direct_answer should be used
    assert "안녕하세요" in result["answer"]


def test_runner_uses_clarify_route_skips_pipeline(tmp_path):
    from src.demo.site_demo_runner import SiteDemoRunner

    payload = (
        '{"route": "clarify", "should_search_site": false, '
        '"confidence": 0.6, "reason": "너무 짧음", '
        '"search_query": "", "direct_answer": "어떤 신청인지 알려주세요"}'
    )
    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="mock",
        output_dir=str(tmp_path),
    )
    runner.router = SiteSearchRouter(provider=MockProvider(payload), site_name=runner.profile.name)
    result = runner.answer("신청은?")
    assert result["route"] == "clarify"
    assert result["should_search_site"] is False
    assert result["answer_mode"] == "clarify"
    assert "어떤 신청인지 알려주세요" in result["answer"]


def test_runner_without_router_falls_back_to_site_search(tmp_path):
    """When no router is attached, the runner must use a positive
    site_search fallback so the search pipeline is still attempted.
    """
    from src.demo.site_demo_runner import SiteDemoRunner

    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="mock",
        output_dir=str(tmp_path),
    )
    # No router attached; runner should fall back to site_search
    result = runner.answer("민원서식 어디서 받아?")
    assert result["route"] == "site_search"
    assert result["should_search_site"] is True
    assert result["answer_mode"] == "retrieval_answer"


# ----------------------------------------------------------------------
# Conversation log: source_weak rule (site_search only)
# ----------------------------------------------------------------------


def test_conversation_log_source_weak_only_for_site_search(tmp_path):
    from src.demo.conversation_log import log_conversation

    log_path = tmp_path / "conversations.jsonl"

    # site_search with no sources → source_weak=True
    r1 = {
        "site_id": "bukgu_gwangju",
        "site_name": "광주광역시 북구청",
        "question": "민원서식",
        "answer": "...",
        "sources": [],
        "route": "site_search",
        "should_search_site": True,
        "route_confidence": 0.84,
        "route_reason": "...",
        "search_query": "민원서식",
        "answer_mode": "retrieval_answer",
        "warnings": [],
    }
    assert log_conversation(r1, log_path=str(log_path)) is True

    # direct_answer with no sources → source_weak=False
    r2 = dict(r1)
    r2["route"] = "direct_answer"
    r2["should_search_site"] = False
    r2["answer_mode"] = "direct_answer"
    r2["question"] = "안녕"
    assert log_conversation(r2, log_path=str(log_path)) is True

    # clarify with no sources → source_weak=False
    r3 = dict(r1)
    r3["route"] = "clarify"
    r3["should_search_site"] = False
    r3["answer_mode"] = "clarify"
    r3["question"] = "신청은?"
    assert log_conversation(r3, log_path=str(log_path)) is True

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    import json as _json
    records = [_json.loads(line) for line in lines]
    assert records[0]["source_weak"] is True
    assert records[1]["source_weak"] is False
    assert records[2]["source_weak"] is False
    assert records[0]["route"] == "site_search"
    assert records[1]["route"] == "direct_answer"
    assert records[2]["route"] == "clarify"
    assert records[0]["route_confidence"] == 0.84
    assert records[0]["answer_mode"] == "retrieval_answer"
    assert records[1]["answer_mode"] == "direct_answer"
    assert records[2]["answer_mode"] == "clarify"


def test_conversation_log_site_search_with_sources_is_not_weak(tmp_path):
    from src.demo.conversation_log import log_conversation

    log_path = tmp_path / "conversations.jsonl"
    result = {
        "site_id": "bukgu_gwangju",
        "site_name": "광주광역시 북구청",
        "question": "민원서식",
        "answer": "...",
        "sources": [{"title": "민원서식", "url": "https://example"}],
        "route": "site_search",
        "should_search_site": True,
        "route_confidence": 0.8,
        "route_reason": "민원",
        "search_query": "민원서식",
        "answer_mode": "retrieval_answer",
        "warnings": [],
    }
    assert log_conversation(result, log_path=str(log_path)) is True

    import json as _json
    line = log_path.read_text(encoding="utf-8").strip()
    record = _json.loads(line)
    assert record["source_weak"] is False
    assert record["sources_count"] == 1
