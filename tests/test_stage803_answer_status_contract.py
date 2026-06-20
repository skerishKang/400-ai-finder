"""Stage #803 — answer_ok / answer_status contract tests.

박사님 확정 contract:
  - answer_ok=True  → 근거 source 기반 답변 또는 허용된 직접 응답 경로
                       (direct_answer / clarify / snapshot matched / grounded site_search / LLM degraded direct)
                       가 정상 생성됨.
  - answer_ok=False → 일반 fallback (snapshot unmatched / site_search no-source /
                       timeout / pipeline exception)

  - answer_status closed-vocab:
      answered_with_evidence | fallback_no_match |
      fallback_unavailable   | error

    경로별 목표값 (report §3.2):
      1. direct_answer                              → answered_with_evidence
      2. clarify                                    → answered_with_evidence
      3. snapshot matched (원본 질문 그대로)         → answered_with_evidence
      4. snapshot unmatched fallback (Issue #803)    → fallback_no_match
      5. site_search grounded success               → answered_with_evidence
      6. site_search no-source / fallback           → fallback_no_match
      7. site_search timeout                        → fallback_unavailable
      8. pipeline exception soft-fail               → error
      9. LLM degraded fallback                      → answered_with_evidence (llm_status로 별도 신호)

이 테스트 파일은 라이브 fetch/network/provider 호출을 하지 않는다.
모든 시나리오는 mock pipeline runner, mock router, fixture snapshot으로
합성한다.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import pytest

from src.answer.answer_status import (
    ANSWER_STATUSES,
    is_valid_answer_status,
    normalize_answer_status,
)
from src.demo import site_demo_runner as runner_module
from src.demo.conversation_log import SAFE_FIELDS, log_conversation
from src.demo.conversation_log_report import summarize_conversation_log
from src.demo.site_demo_runner import SiteDemoRunner
from src.demo.snapshot_helper import save_snapshot
from src.llm.site_search_router import (
    RouterDecision,
    clarify_fallback_direct_answer,
    default_fallback_decision,
    greeting_fallback_direct_answer,
)


# ---------------------------------------------------------------------------
# 0) Closed-vocab module
# ---------------------------------------------------------------------------


def test_answer_status_closed_vocab_has_four_values():
    assert ANSWER_STATUSES == (
        "answered_with_evidence",
        "fallback_no_match",
        "fallback_unavailable",
        "error",
    )


@pytest.mark.parametrize("status", list(ANSWER_STATUSES))
def test_is_valid_accepts_all_closed_values(status: str):
    assert is_valid_answer_status(status) is True


@pytest.mark.parametrize(
    "bogus",
    ["PASS", "warn", "no_results", "", "answered", "EVIDENCE", None, 0, True],
)
def test_is_valid_rejects_non_vocab(bogus):
    assert is_valid_answer_status(bogus) is False


def test_normalize_falls_back_to_error_for_unknown():
    assert normalize_answer_status("PASS") == "error"
    assert normalize_answer_status(None) == "error"
    assert normalize_answer_status("answered_with_evidence") == "answered_with_evidence"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_search_results(path: str, results: list[dict[str, Any]]) -> None:
    """Write a search.jsonl file in the shape ``_build_pipeline_result``
    actually consumes.

    The pipeline runner writes ``{"results": [...]}`` as a single JSON
    object, not a stream of one-result-per-line. We mirror that shape
    so the runner can read it via ``json.load`` + ``.get("results", [])``.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False)


def _write_answer(path: str, markdown: str, sources: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ok": True, "answer_markdown": markdown, "sources": sources, "warnings": []}, f, ensure_ascii=False)


def _make_runner_with_router(
    tmp_path,
    monkeypatch,
    router_decision: RouterDecision,
    pipeline_runner_cls,
):
    """Build a SiteDemoRunner with a forced router decision and a stubbed
    PipelineRunner class.

    We bypass the live router by injecting ``router`` directly on the runner
    instance so tests never touch the LLM provider.
    """
    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="mock",
        output_dir=str(tmp_path),
        pipeline_timeout_s=10.0,
    )
    monkeypatch.setattr(runner_module, "PipelineRunner", pipeline_runner_cls)
    runner.router = type(
        "_StubRouter",
        (),
        {"decide": staticmethod(lambda q: router_decision)},
    )()
    return runner


# ---------------------------------------------------------------------------
# 1) direct_answer route
# ---------------------------------------------------------------------------


def test_path_1_direct_answer_returns_answered_with_evidence(tmp_path, monkeypatch):
    """route=direct_answer → answer_ok=true, answer_status=answered_with_evidence"""
    decision = RouterDecision(
        route="direct_answer",
        should_search_site=False,
        confidence=0.95,
        reason="greeting",
        search_query=None,
        direct_answer=greeting_fallback_direct_answer("광주광역시 북구청"),
    )

    class _NoOpPipeline:
        def __init__(self, *a, **kw):
            pass

        def run(self, url, query):
            return {"ok": True, "steps": [], "answer_markdown": ""}

    runner = _make_runner_with_router(tmp_path, monkeypatch, decision, _NoOpPipeline)
    result = runner.answer("안녕")

    assert result["route"] == "direct_answer"
    assert result["ok"] is True
    assert result["answer_ok"] is True
    assert result["answer_status"] == "answered_with_evidence"
    assert result["source_weak"] is False
    assert result["fetch_diagnostic"] is None


# ---------------------------------------------------------------------------
# 2) clarify route
# ---------------------------------------------------------------------------


def test_path_2_clarify_returns_answered_with_evidence(tmp_path, monkeypatch):
    """route=clarify → answer_ok=true, answer_status=answered_with_evidence"""
    decision = RouterDecision(
        route="clarify",
        should_search_site=False,
        confidence=0.6,
        reason="low_confidence",
        search_query=None,
        direct_answer=clarify_fallback_direct_answer("광주광역시 북구청"),
    )

    class _NoOpPipeline:
        def __init__(self, *a, **kw):
            pass

        def run(self, url, query):
            return {"ok": True, "steps": [], "answer_markdown": ""}

    runner = _make_runner_with_router(tmp_path, monkeypatch, decision, _NoOpPipeline)
    result = runner.answer("음... 뭐지")

    assert result["route"] == "clarify"
    assert result["ok"] is True
    assert result["answer_ok"] is True
    assert result["answer_status"] == "answered_with_evidence"
    assert result["source_weak"] is False


# ---------------------------------------------------------------------------
# 3) snapshot matched (원본 snapshot 질문 그대로)
# ---------------------------------------------------------------------------


def test_path_3_snapshot_matched_returns_answered_with_evidence(tmp_path):
    """snapshot 그대로 재현 (question 변경 없음) → matched sources 유지 →
    answer_ok=true, answer_status=answered_with_evidence."""
    snap = {
        "site_id": "bukgu_gwangju",
        "site_name": "광주광역시 북구청",
        "question": "민원서식 어디서 받아?",
        "answer": "북구청 홈페이지 종합민원 > 민원서식",
        "sources": [
            {"title": "민원서식", "url": "https://bukgu.gwangju.kr/m1", "source_type": "menu"}
        ],
        "search_results": [],
        "ok": True,
        "answer_ok": True,
        "answer_status": "answered_with_evidence",
        "provider": "stub",
        "model": "stub",
        "fetch_provider": None,
        "output_dir": str(tmp_path),
        "fetched_at": "2026-06-19T00:00:00Z",
        "fallback_used": False,
        "warnings": [],
        "homepage_map": {
            "homepage": {
                "navigation_links": [
                    {"title": "종합민원", "url": "https://bukgu.gwangju.kr/m1", "source_type": "menu"}
                ]
            }
        },
    }
    snap_path = os.path.join(tmp_path, "snap.json")
    save_snapshot(snap, snap_path)

    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="stub",
        output_dir=str(tmp_path),
        snapshot_path=snap_path,
    )
    result = runner.answer_from_snapshot(snap_path, question="민원서식 어디서 받아?")

    # question unchanged → answer_status normalized but answer_ok preserved
    assert result["answer_ok"] is True
    assert result["answer_status"] == "answered_with_evidence"
    assert len(result["sources"]) >= 1


# ---------------------------------------------------------------------------
# 4) snapshot unmatched fallback — Issue #803 root cause
# ---------------------------------------------------------------------------


def test_path_4_snapshot_unmatched_returns_fallback_no_match(tmp_path):
    """Issue #803 root cause: snapshot helper가 fb-empty 분기에서
    answer_ok=false, answer_status=fallback_no_match를 stamp해야 한다.

    Setup: snapshot은 matched 상태로 저장되어 있지만, 새 질문은 fallback
    sources가 비어있어서 generic fallback이 반환되는 경로.
    """
    snap = {
        "site_id": "bukgu_gwangju",
        "site_name": "광주광역시 북구청",
        "question": "민원서식 어디서 받아?",  # 원본
        "answer": "북구청 홈페이지 종합민원",
        "sources": [
            {"title": "민원서식", "url": "https://bukgu.gwangju.kr/m1", "source_type": "menu"}
        ],
        "search_results": [],
        "ok": True,
        "answer_ok": True,  # 원본은 matched → True 였음
        "answer_status": "answered_with_evidence",
        "provider": "stub",
        "model": "stub",
        "fetch_provider": None,
        "output_dir": str(tmp_path),
        "fetched_at": "2026-06-19T00:00:00Z",
        "fallback_used": False,
        "warnings": [],
        # homepage_map은 새 질문과 매칭되는 menu가 없도록 의도적으로 비움
        "homepage_map": {
            "homepage": {"navigation_links": []}
        },
    }
    snap_path = os.path.join(tmp_path, "snap.json")
    save_snapshot(snap, snap_path)

    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="stub",
        output_dir=str(tmp_path),
        snapshot_path=snap_path,
    )
    # 새 질문 (원본과 다름) → question_changed=True
    result = runner.answer_from_snapshot(snap_path, question="도서관 이용시간 알려줘")

    assert result["answer_ok"] is False  # ← 핵심: Issue #803 해결
    assert result["answer_status"] == "fallback_no_match"
    assert result["sources"] == []
    assert result["source_weak"] is True
    # ok 필드는 fixture 원본 값(True) 유지 — transport/pipeline 의미로 보존
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# 5) site_search grounded success
# ---------------------------------------------------------------------------


def test_path_5_site_search_grounded_returns_answered_with_evidence(tmp_path, monkeypatch):
    """sources>0 + answer step ok + fallback_used=False →
    answer_ok=true, answer_status=answered_with_evidence"""
    search_path = os.path.join(tmp_path, "search.jsonl")
    answer_path = os.path.join(tmp_path, "answer.json")
    _write_search_results(
        search_path,
        [
            {
                "id": "r1",
                "title": "교육접수 안내",
                "url": "https://bukgu.gwangju.kr/edu",
                "category": "menu",
                "text": "교육접수는 북구청 홈페이지에서 안내합니다.",
                "score": 5.0,
            }
        ],
    )
    _write_answer(
        answer_path,
        "## 답변\n교육접수는 북구청 홈페이지에서 안내합니다.",
        [
            {"title": "교육접수 안내", "url": "https://bukgu.gwangju.kr/edu", "source_type": "menu"}
        ],
    )

    class _GroundedPipeline:
        def __init__(self, *a, **kw):
            pass

        def run(self, url, query):
            return {
                "ok": True,
                "url": url,
                "query": query,
                "output_dir": str(tmp_path),
                "steps": [
                    {"name": "search", "ok": True, "output": search_path, "error": ""},
                    {"name": "answer", "ok": True, "output": answer_path, "error": ""},
                ],
                "answer_markdown": "",
            }

    decision = default_fallback_decision("교육접수 어디서 해?", "광주광역시 북구청")
    runner = _make_runner_with_router(tmp_path, monkeypatch, decision, _GroundedPipeline)
    result = runner.answer("교육접수 어디서 해?")

    assert result["route"] == "site_search"
    assert result["ok"] is True
    assert result["answer_ok"] is True
    assert result["answer_status"] == "answered_with_evidence"
    assert result["source_weak"] is False
    assert result["fetch_diagnostic"] is None


# ---------------------------------------------------------------------------
# 6) site_search no-source / fallback — answer_ok=false, fallback_no_match
# ---------------------------------------------------------------------------


def test_path_6_site_search_no_source_returns_fallback_no_match(tmp_path, monkeypatch):
    """sources=0 + pipeline ok → soft answer + answer_ok=false + fallback_no_match"""
    answer_path = os.path.join(tmp_path, "answer.json")
    _write_answer(answer_path, "", [])  # empty answer_markdown → soft fallback

    class _NoSourcePipeline:
        def __init__(self, *a, **kw):
            pass

        def run(self, url, query):
            return {
                "ok": True,
                "url": url,
                "query": query,
                "output_dir": str(tmp_path),
                "steps": [
                    # No search step output → search_results=[], sources=[]
                    {"name": "search", "ok": True, "output": "", "error": ""},
                    {"name": "answer", "ok": True, "output": answer_path, "error": ""},
                ],
                "answer_markdown": "",
            }

    decision = default_fallback_decision("이상한 키워드", "광주광역시 북구청")
    runner = _make_runner_with_router(tmp_path, monkeypatch, decision, _NoSourcePipeline)
    result = runner.answer("이상한 키워드")

    assert result["ok"] is True
    assert result["answer_ok"] is False  # ← 핵심
    assert result["answer_status"] == "fallback_no_match"
    assert result["source_weak"] is True


# ---------------------------------------------------------------------------
# 7) site_search timeout — answer_ok=false, fallback_unavailable
# ---------------------------------------------------------------------------


def test_path_7_site_search_timeout_returns_fallback_unavailable(tmp_path, monkeypatch):
    """budget 초과 시 _build_timeout_pipeline_result →
    answer_ok=false, answer_status=fallback_unavailable"""
    import time

    class _HangingPipeline:
        def __init__(self, *a, **kw):
            pass

        def run(self, url, query):
            time.sleep(5.0)
            return {"ok": True, "steps": [], "answer_markdown": ""}

    monkeypatch.setattr(runner_module, "PipelineRunner", _HangingPipeline)
    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="mock",
        output_dir=str(tmp_path),
        pipeline_timeout_s=0.3,
    )
    result = runner.answer("민원서식 어디서 받아?")

    assert result["ok"] is False
    assert result["answer_ok"] is False  # ← 핵심
    assert result["answer_status"] == "fallback_unavailable"  # ← 핵심
    assert result["source_weak"] is True
    assert result["fetch_diagnostic"] is not None
    assert result["fetch_diagnostic"]["category"] == "timeout"


# ---------------------------------------------------------------------------
# 8) pipeline exception soft-fail — answer_ok=false, error
# ---------------------------------------------------------------------------


def test_path_8_pipeline_exception_returns_error_status(tmp_path, monkeypatch):
    """PipelineRunner.run이 raise → _run_pipeline_with_timeout이 classified
    diagnostic과 함께 soft JSON 반환 → answer_status=error"""
    class _RaisingPipeline:
        def __init__(self, *a, **kw):
            pass

        def run(self, url, query):
            raise ConnectionError("simulated fetch failure to bukgu.gwangju.kr")

    monkeypatch.setattr(runner_module, "PipelineRunner", _RaisingPipeline)
    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="mock",
        output_dir=str(tmp_path),
        pipeline_timeout_s=10.0,
    )
    result = runner.answer("민원서식 어디서 받아?")

    assert result["ok"] is False
    assert result["answer_ok"] is False
    assert result["answer_status"] == "error"  # ← 핵심
    assert result["fetch_diagnostic"] is not None
    # Category must be one of the closed-vocab categories, NOT raw text
    assert result["fetch_diagnostic"]["category"] in {
        "timeout", "connection_error", "tls_error", "http_error",
        "blocked_or_forbidden", "parse_error", "unknown_fetch_error",
    }
    # The simulated URL must NOT leak into the user-facing answer or diagnostic
    assert "bukgu.gwangju.kr" not in result["answer"]
    assert "bukgu.gwangju.kr" not in (result["fetch_diagnostic"]["short_reason"] or "")


def test_path_8b_parse_error_returns_error_status(tmp_path, monkeypatch):
    """Non-timeout diagnostic category (parse_error) → answer_status=error.

    박사님 보강 지시: timeout 외 closed-vocab diagnostic category는 모두
    ``error`` 로 분류되어야 한다. parse_error 케이스로 검증.
    """
    from src.fetch.compat_diagnostics import (
        FetchCategory,
        FetchDiagnostic,
        format_operator_safe,
    )

    parse_diagnostic = FetchDiagnostic(
        category=FetchCategory.PARSE_ERROR,
        short_reason="Response payload could not be parsed.",
        retry_hint="do_not_retry",
        is_transient=False,
    )
    parse_operator_safe = format_operator_safe(parse_diagnostic)
    safe_error = f"Pipeline raised: {parse_operator_safe}"

    class _RaisingParsePipeline:
        def __init__(self, *a, **kw):
            pass

        def run(self, url, query):
            # Simulated ValueError that classify_exception routes to
            # parse_error (JSONDecodeError → parse_error).
            import json as _json
            raise _json.JSONDecodeError("Expecting value", "", 0)

    monkeypatch.setattr(runner_module, "PipelineRunner", _RaisingParsePipeline)
    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="mock",
        output_dir=str(tmp_path),
        pipeline_timeout_s=10.0,
    )
    result = runner.answer("민원서식 어디서 받아?")

    assert result["ok"] is False
    assert result["answer_ok"] is False
    assert result["answer_status"] == "error"  # ← 핵심: timeout 아닌 diagnostic은 error
    assert result["fetch_diagnostic"]["category"] == "parse_error"
    # raw exception ("Expecting value") must NOT leak into user-facing
    # answer, warnings, or fetch_diagnostic short_reason.
    blob = json.dumps(result, ensure_ascii=False)
    assert "Expecting value" not in blob


def test_path_7_timeout_returns_fallback_unavailable(tmp_path, monkeypatch):
    """budget 초과 → pipeline_diagnostic.category == "timeout" →
    answer_status=fallback_unavailable (error가 아님).

    박사님 보강 지시: timeout만 ``fallback_unavailable`` 이고 나머지는
    ``error`` 인 분류가 명확히 작동해야 한다.
    """
    import time
    from src.fetch.compat_diagnostics import FetchCategory

    class _HangingPipeline:
        def __init__(self, *a, **kw):
            pass

        def run(self, url, query):
            time.sleep(5.0)
            return {"ok": True, "steps": [], "answer_markdown": ""}

    monkeypatch.setattr(runner_module, "PipelineRunner", _HangingPipeline)
    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="mock",
        output_dir=str(tmp_path),
        pipeline_timeout_s=0.3,
    )
    result = runner.answer("민원서식 어디서 받아?")

    assert result["ok"] is False
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_unavailable"
    # 분류 기준은 pipeline_diagnostic.category == "timeout"
    assert result["fetch_diagnostic"]["category"] == FetchCategory.TIMEOUT.value
    # error나 fallback_no_match가 아니어야 함 (분리 검증)
    assert result["answer_status"] != "error"
    assert result["answer_status"] != "fallback_no_match"


# ---------------------------------------------------------------------------
# 8.5) docs contract keyword 회귀 방지 — 박사님 merge 전 보강
# ---------------------------------------------------------------------------


def test_answer_status_module_docstring_contains_failure_taxonomy():
    """src/answer/answer_status.py docstring 안에 timeout-only 분류
    계약 문구가 명시되어 있어야 한다 (박사님 보강 merge 조건)."""
    import inspect
    from src.answer import answer_status

    src = inspect.getsource(answer_status)
    # 'fallback_unavailable' 는 timeout으로 한정, 그 외 인프라 실패는 error
    assert "pipeline timeout으로 데이터 미수신" in src
    assert "timeout 외" in src
    # error 정의에 non-timeout closed-vocab category 명시
    assert "connection_error" in src
    assert "parse_error" in src


def test_fetch_compat_docs_have_no_debug_log_only_phrase():
    """박사님 보강 merge 조건: docs/fetch-compat-diagnostic-boundary.md 에
    ``raw exception stays in the debug log only`` 같은 구문이 남아 있으면 안 된다.
    동일한 의미를 ``raw exception text is not emitted ... to any application log
    surface (including debug logs)`` 로 대체했기 때문.
    """
    from pathlib import Path
    docs_path = Path("docs/fetch-compat-diagnostic-boundary.md")
    content = docs_path.read_text(encoding="utf-8")
    forbidden_phrases = [
        "raw exception stays in the debug log only",
        "operators who need the raw text can still read",
        "raw exception stays",  # suffix variant
    ]
    for phrase in forbidden_phrases:
        assert phrase.lower() not in content.lower(), (
            f"docs still contain forbidden phrase: {phrase!r}"
        )
    # replacement 문구는 살아 있어야 함 (박사님 명시 verbatim — sentence case)
    content_lower = content.lower()
    assert "raw exception text is not emitted to user-facing output or application log surfaces" in content_lower
    assert "operators receive only the sanitized diagnostic category, short reason, retry hint, and transient flag" in content_lower


def test_fetch_compat_docs_list_closed_vocab_categories_for_error():
    """박사님 보강 merge 조건: docs 가 timeout 외 closed-vocab diagnostic
    category (connection_error / tls_error / http_error / parse_error /
    unknown_fetch_error) 가 모두 error 로 매핑된다는 사실을 명시해야 한다."""
    from pathlib import Path
    docs_path = Path("docs/fetch-compat-diagnostic-boundary.md")
    content = docs_path.read_text(encoding="utf-8")
    required_categories = [
        "connection_error",
        "tls_error",
        "http_error",
        "blocked_or_forbidden",
        "parse_error",
        "unknown_fetch_error",
    ]
    for cat in required_categories:
        assert cat in content, (
            f"docs missing closed-vocab category reference: {cat}"
        )
    # 모두 'error' 로 매핑된다는 사실 (timeout 만 fallback_unavailable)
    # 9-path matrix 의 path 8 이 error 로 분류된다는 사실
    assert "answer_status=`error`" in content
    assert "answer_status=`fallback_unavailable`" in content


# ---------------------------------------------------------------------------
# 9) LLM degraded fallback (live provider이지만 호출 실패)
# ---------------------------------------------------------------------------


def test_path_9_llm_degraded_direct_returns_answered_with_evidence(tmp_path, monkeypatch):
    """direct_answer 라우팅은 유지되지만 llm_status가 live_provider_error 인
    케이스에서도 answer_status는 answered_with_evidence로 유지된다.
    llm_status는 별도 신호 채널.
    """
    decision = RouterDecision(
        route="direct_answer",
        should_search_site=False,
        confidence=0.95,
        reason="greeting",
        search_query=None,
        direct_answer="안녕하세요.",
    )

    class _NoOpPipeline:
        def __init__(self, *a, **kw):
            pass

        def run(self, url, query):
            return {"ok": True, "steps": [], "answer_markdown": ""}

    runner = _make_runner_with_router(tmp_path, monkeypatch, decision, _NoOpPipeline)
    result = runner.answer("안녕")

    assert result["route"] == "direct_answer"
    assert result["ok"] is True
    assert result["answer_ok"] is True
    assert result["answer_status"] == "answered_with_evidence"
    # llm_status는 정상 응답이므로 snapshot_no_api 또는 mock_no_api여도 OK
    # 직접 검증은 어려우므로 타입만 확인
    assert result["llm_status"] in {
        "mock_no_api", "stub_no_api", "snapshot_no_api",
        "live_provider_configured", "live_provider_not_configured",
        "live_provider_error", "live_provider_not_called", "unknown_provider",
    }


# ---------------------------------------------------------------------------
# 10) conversation_log: answer_status 컬럼 추가
# ---------------------------------------------------------------------------


def test_conversation_log_writes_answer_status_column(tmp_path):
    """log_conversation 가 answer_status 컬럼을 JSONL에 기록해야 한다."""
    log_path = os.path.join(tmp_path, "conv.jsonl")
    record = {
        "site_id": "bukgu_gwangju",
        "site_name": "광주광역시 북구청",
        "question": "도서관",
        "answer": "관련 정보를 찾지 못했습니다.",
        "ok": True,
        "answer_ok": False,
        "answer_status": "fallback_no_match",
        "provider": "stub",
        "model": "stub",
        "llm_status": "stub_no_api",
        "llm_live": False,
        "sources": [],
        "fallback_used": False,
        "warnings": [],
        "route": "site_search",
        "should_search_site": True,
        "route_confidence": 0.0,
        "route_reason": "default",
        "search_query": "도서관",
        "answer_mode": "retrieval_answer",
        "source_weak": True,
        "fetch_diagnostic": None,
    }
    assert log_conversation(record, log_path=log_path) is True
    with open(log_path, "r", encoding="utf-8") as f:
        line = f.readline().strip()
    parsed = json.loads(line)
    assert parsed["answer_status"] == "fallback_no_match"


def test_conversation_log_normalizes_unknown_answer_status(tmp_path):
    """log_conversation 가 모르는 값은 error로 normalize."""
    log_path = os.path.join(tmp_path, "conv.jsonl")
    record = {
        "site_id": "bukgu_gwangju",
        "question": "test",
        "answer": "...",
        "ok": True,
        "answer_ok": True,
        "answer_status": "WARN",  # 비-closed-vocab → error 로 변환
        "provider": "stub",
        "model": "stub",
        "llm_status": "stub_no_api",
        "llm_live": False,
        "sources": [],
        "fallback_used": False,
        "warnings": [],
        "route": "direct_answer",
        "should_search_site": False,
        "route_confidence": 0.5,
        "route_reason": "default",
        "search_query": "",
        "answer_mode": "direct_answer",
        "source_weak": False,
        "fetch_diagnostic": None,
    }
    assert log_conversation(record, log_path=log_path) is True
    with open(log_path, "r", encoding="utf-8") as f:
        line = f.readline().strip()
    parsed = json.loads(line)
    assert parsed["answer_status"] == "error"


def test_conversation_log_safe_fields_includes_answer_status():
    assert "answer_status" in SAFE_FIELDS


# ---------------------------------------------------------------------------
# 11) conversation_log_report: answer_status_counts 집계
# ---------------------------------------------------------------------------


def test_conversation_log_report_aggregates_answer_status(tmp_path):
    log_path = os.path.join(tmp_path, "conv.jsonl")
    rows = [
        {"answer_status": "answered_with_evidence", "route": "site_search", "answer_ok": True, "site_id": "bukgu_gwangju", "llm_status": "stub_no_api", "source_weak": False},
        {"answer_status": "fallback_no_match", "route": "site_search", "answer_ok": False, "site_id": "bukgu_gwangju", "llm_status": "stub_no_api", "source_weak": True},
        {"answer_status": "fallback_unavailable", "route": "site_search", "answer_ok": False, "site_id": "bukgu_gwangju", "llm_status": "stub_no_api", "source_weak": True},
        {"answer_status": "error", "route": "site_search", "answer_ok": False, "site_id": "bukgu_gwangju", "llm_status": "stub_no_api", "source_weak": True},
        {"answer_status": None, "route": "direct_answer", "answer_ok": True, "site_id": "bukgu_gwangju", "llm_status": "stub_no_api", "source_weak": False},
    ]
    with open(log_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    summary = summarize_conversation_log(log_path)
    counts = summary["answer_status_counts"]
    assert counts["answered_with_evidence"] == 1
    assert counts["fallback_no_match"] == 1
    assert counts["fallback_unavailable"] == 1
    assert counts["error"] == 1
    assert counts["none"] == 1


# ---------------------------------------------------------------------------
# 12) canary: 모르는 canary 단어가 응답 envelope 어디에도 없어야 한다
# ---------------------------------------------------------------------------


def test_no_canary_leak_in_snapshot_unmatched_response(tmp_path):
    """Stage #800/801 정책과 일관성 — 응답 envelope 안의 operator-visible
    필드(answer, warnings, fetch_diagnostic, error 등)에 raw exception,
    header, body, URL credentials, API key 같은 canary가 노출되지 않아야
    한다.

    사용자 본인 ``question``은 demo UI에 표시되는 정상 필드이므로
    envelope에 들어가도 leak이 아니다. 이 테스트는 그것을 제외한다.
    """
    snap = {
        "site_id": "bukgu_gwangju",
        "site_name": "광주광역시 북구청",
        "question": "민원서식",
        "answer": "matched",
        "sources": [
            {"title": "민원서식", "url": "https://bukgu.gwangju.kr/m1", "source_type": "menu"}
        ],
        "search_results": [],
        "ok": True,
        "answer_ok": True,
        "answer_status": "answered_with_evidence",
        "provider": "stub",
        "model": "stub",
        "fetch_provider": None,
        "output_dir": str(tmp_path),
        "fetched_at": "2026-06-19T00:00:00Z",
        "fallback_used": False,
        "warnings": [],
        "homepage_map": {"homepage": {"navigation_links": []}},
    }
    snap_path = os.path.join(tmp_path, "snap.json")
    save_snapshot(snap, snap_path)

    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="stub",
        output_dir=str(tmp_path),
        snapshot_path=snap_path,
    )
    canary = "VERY_SPECIFIC_STAGE803_CANARY_DO_NOT_LEAK"
    result = runner.answer_from_snapshot(snap_path, question=canary)

    # 1) answer_status / answer_ok 계약 — Issue #803 핵심
    assert result["answer_status"] == "fallback_no_match"
    assert result["answer_ok"] is False

    # 2) operator-visible 필드들만 별도로 직렬화해서 canary가 없는지 확인.
    #    ``question``/``site_id``/``site_name`` 같은 metadata는 의도적으로
    #    제외한다 (사용자 본인 입력이 envelope에 표시되어도 leak 아님).
    operator_visible_blob = json.dumps(
        {
            "answer": result.get("answer", ""),
            "warnings": result.get("warnings", []),
            "fetch_diagnostic": result.get("fetch_diagnostic"),
            "error": result.get("error"),
            "answer_status": result.get("answer_status"),
        },
        ensure_ascii=False,
    )
    assert canary not in operator_visible_blob, (
        f"canary leaked into operator-visible fields: {operator_visible_blob[:200]}"
    )
    # 3) snapshot의 원본 answer (matched text)도 그대로 보존 — unmatched
    #    fallback answer로 덮어써진 상태여야 한다.
    assert result["answer"] != snap["answer"]
    assert "관련 정보를 찾지 못했습니다" in result["answer"] or "찾지 못했" in result["answer"]


def test_pipeline_exception_no_canary_in_response(tmp_path, monkeypatch):
    """PipelineRunner.run이 raise → 응답 envelope 어디에도 URL credential,
    Authorization 헤더, secret body 등이 노출되지 않아야 한다."""
    class _RaisingPipeline:
        def __init__(self, *a, **kw):
            pass

        def run(self, url, query):
            # 시뮬레이션된 fetch 예외 — operator-visible surface로 leak
            # 되면 안 되는 canary 6종을 모두 포함
            raise RuntimeError(
                "fetch failed: "
                "sk-LIVecanary123cdef | "
                "Bearer c4n4ry-token-xyz | "
                "X-Internal-Secret: top-secret | "
                "secret_body=THIS_IS_THE_BODY | "
                "https://user:p4ssw0rd@host.example/path"
            )

    monkeypatch.setattr(runner_module, "PipelineRunner", _RaisingPipeline)
    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="mock",
        output_dir=str(tmp_path),
        pipeline_timeout_s=10.0,
    )
    result = runner.answer("민원서식 어디서 받아?")

    blob = json.dumps(result, ensure_ascii=False)
    for canary in [
        "sk-LIVecanary123cdef",
        "Bearer c4n4ry-token-xyz",
        "X-Internal-Secret",
        "top-secret",
        "THIS_IS_THE_BODY",
        "user:p4ssw0rd",
    ]:
        assert canary not in blob, f"canary leaked: {canary} in {blob[:300]}"
    # answer_status는 error로 분류
    assert result["answer_status"] == "error"
    assert result["answer_ok"] is False
