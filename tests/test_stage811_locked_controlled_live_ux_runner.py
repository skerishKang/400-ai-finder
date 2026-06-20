"""No-live tests for the locked controlled-live UX runner.

Stage #811 introduced the dry-run MVP. Stage #813 extends it with the
double opt-in gate, the test-only ``execution_boundary`` seam, and
the Stage #806 boundary-result state correction.
"""

from __future__ import annotations

import ast
import importlib
import socket
import subprocess
from pathlib import Path
from typing import Any, Callable

import pytest

from src.demo import controlled_live_ux_runner as runner_module
from src.demo.controlled_live_smoke_contract import (
    APPROVED_EXECUTION_MODE,
    APPROVED_FETCH_PROVIDER,
    APPROVED_LLM_PROVIDER,
    APPROVED_SITE_ID,
)
from src.demo.controlled_live_ux_runner import (
    CONTROLLED_LIVE_REQUESTED_MODE,
    DRY_RUN_MODE,
    INVALID_REQUEST_CODE,
    LockedControlledLiveUxError,
    LockedControlledLiveUxRequest,
    LockedControlledLiveUxResponse,
    MAX_QUESTION_LEN,
    QUESTION_INVALID_CODE,
    REQUIRED_ACKNOWLEDGEMENT,
    run_locked_controlled_live_ux,
)


FORBIDDEN_IMPORTS = {
    "requests", "httpx", "urllib", "urllib.request", "subprocess",
    "threading", "asyncio", "concurrent", "concurrent.futures",
    "firecrawl", "playwright", "scrapy", "crawl4ai", "browser_use", "browser",
}


SECRET_CANARIES = (
    "Bearer secret-token",
    "Authorization: Bearer token-abc123",
    "https://user:pass@example.test/path",
    "header-like: x-api-key=abc123",
    "body-like secret=abc123",
)


def _request(question="민원서식 어디서 받아?", *, allow=False, ack=None):
    return LockedControlledLiveUxRequest(
        question=question, allow_controlled_live=allow, acknowledgement=ack,
    )


def _opt_in_request():
    return LockedControlledLiveUxRequest(
        question="민원서식 어디서 받아?",
        allow_controlled_live=True,
        acknowledgement=REQUIRED_ACKNOWLEDGEMENT,
    )


def _check_plan(plan):
    assert plan.site_id == APPROVED_SITE_ID
    assert plan.fetch_provider == APPROVED_FETCH_PROVIDER
    assert plan.llm_provider == APPROVED_LLM_PROVIDER
    assert plan.max_pages == 1
    assert plan.max_depth == 0
    assert plan.max_sitemaps == 0
    assert plan.max_enrich_pages == 0
    assert plan.retry_count == 0
    assert plan.request_timeout_s == 5.0
    assert plan.total_budget_s == 10.0
    assert plan.persist_scenarios is False
    assert plan.persist_snapshots is False
    assert plan.persist_cache is False
    assert plan.persist_config is False
    assert plan.persist_source_grounding is False
    assert plan.temp_only_output is True
    assert plan.deterministic_cleanup is True
    assert plan.audit_path is None
    assert plan.retain_artifacts is False
    assert plan.execution_mode == APPROVED_EXECUTION_MODE
    assert plan.isolated_process_group is True
    assert plan.kill_process_group_on_timeout is True
    assert plan.explicit_user_post_count == 1
    assert plan.separate_fetch_attempts_observable is True


def _evidence_boundary():
    def _boundary(plan):
        return {
            "ok": True,
            "answer_ok": True,
            "answer_markdown": "북구청 홈페이지에서 민원서식을 내려받을 수 있습니다.",
            "sources": [
                {
                    "id": "r1",
                    "title": "민원서식 안내",
                    "url": "https://bukgu.gwangju.kr/apply",
                    "category": "menu",
                    "text": "민원서식은 북구청 홈페이지에서 내려받을 수 있습니다.",
                    "score": 5.0,
                }
            ],
        }
    return _boundary


def test_dry_run_returns_fixed_plan_and_envelope():
    response = run_locked_controlled_live_ux(request=_request())
    assert isinstance(response, LockedControlledLiveUxResponse)
    assert response.mode == DRY_RUN_MODE
    assert response.execution_allowed is False
    _check_plan(response.plan)
    result = response.result
    assert result["ok"] is True
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_no_match"
    assert result["source_weak"] is True
    assert result["sources"] == []
    assert result["fetch_diagnostic"] is None


@pytest.mark.parametrize("allow, ack", [
    (False, None),
    (False, ""),
    (False, REQUIRED_ACKNOWLEDGEMENT),
    (True, None),
    (True, ""),
    (True, "wrong-acknowledgement"),
    (True, "i_acknowledge_controlled_live"),
    (True, " I_ACKNOWLEDGE_CONTROLLED_LIVE"),
])
def test_dry_run_for_opt_in_not_met_never_invokes_boundary(allow, ack):
    calls = []
    def _boundary(plan):
        calls.append(plan)
        return _evidence_boundary()(plan)
    response = run_locked_controlled_live_ux(
        request=_request(allow=allow, ack=ack),
        execution_boundary=_boundary,
    )
    assert response.mode == DRY_RUN_MODE
    assert response.execution_allowed is False
    _check_plan(response.plan)
    assert calls == []


def test_opt_in_met_without_boundary_returns_execution_not_enabled():
    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=None,
    )
    assert response.mode == CONTROLLED_LIVE_REQUESTED_MODE
    assert response.execution_allowed is True
    _check_plan(response.plan)
    result = response.result
    assert result["ok"] is False
    assert result["answer_ok"] is False
    assert result["answer_status"] == "error"
    assert result["source_weak"] is True
    assert result["sources"] == []
    assert result["fetch_diagnostic"] is None


def test_opt_in_met_with_boundary_invokes_exactly_once():
    calls = []
    def _boundary(plan):
        calls.append(plan)
        return _evidence_boundary()(plan)
    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )
    assert len(calls) == 1
    received = calls[0]
    assert isinstance(received, type(response.plan))
    _check_plan(received)


def test_boundary_with_evidence_returns_answered_with_evidence():
    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_evidence_boundary(),
    )
    result = response.result
    assert result["ok"] is True
    assert result["answer_ok"] is True
    assert result["answer_status"] == "answered_with_evidence"
    assert result["source_weak"] is False
    assert result["sources"] == [{"id": "r1", "url": "https://bukgu.gwangju.kr/apply"}]


def test_boundary_sources_only_with_blank_answer_returns_fallback():
    def _boundary(plan):
        return {
            "ok": True,
            "answer_ok": True,
            "answer_markdown": "   \n\t",
            "sources": [{"id": "r1", "url": "https://bukgu.gwangju.kr/apply"}],
        }
    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )
    result = response.result
    assert result["ok"] is True
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_no_match"
    assert result["source_weak"] is True


def test_boundary_answer_ok_false_returns_fallback():
    def _boundary(plan):
        return {
            "ok": True,
            "answer_ok": False,
            "answer_markdown": "real answer text",
            "sources": [{"id": "r1", "url": "https://bukgu.gwangju.kr/apply"}],
        }
    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )
    result = response.result
    assert result["ok"] is True
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_no_match"
    assert result["source_weak"] is True


@pytest.mark.parametrize("answer_markdown", [
    None, "", "   ", ["not", "a", "string"], {"key": "value"}, 42, True,
])
def test_boundary_non_string_or_missing_answer_markdown_returns_fallback(answer_markdown):
    def _boundary(plan):
        return {
            "ok": True,
            "answer_ok": True,
            "answer_markdown": answer_markdown,
            "sources": [{"id": "r1", "url": "https://bukgu.gwangju.kr/apply"}],
        }
    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )
    result = response.result
    assert result["ok"] is True
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_no_match"
    assert result["source_weak"] is True


@pytest.mark.parametrize("sources_value", [
    [], None, "not a list", [{"id": ""}], [{"url": "https://bukgu.gwangju.kr/apply"}],
])
def test_boundary_empty_or_invalid_sources_returns_fallback(sources_value):
    def _boundary(plan):
        return {
            "ok": True,
            "answer_ok": True,
            "answer_markdown": "real answer",
            "sources": sources_value,
        }
    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )
    result = response.result
    assert result["ok"] is True
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_no_match"
    assert result["source_weak"] is True


# --- Fix #1: URL-less source must NOT count as evidence -----------------

def test_boundary_source_with_id_but_no_url_returns_fallback():
    """A source with a valid id but no url is not enough for evidence.

    PR #816 review: ``id`` alone is insufficient — the runner must
    require a nonblank string ``url`` alongside ``id``. With the url
    missing, ``sources`` collapses to ``[]`` and the response is
    ``fallback_no_match`` (not ``answered_with_evidence``).
    """
    def _boundary(plan):
        return {
            "ok": True,
            "answer_ok": True,
            "answer_markdown": "정상 답변",
            "sources": [{"id": "source-only-id"}],
        }

    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )

    result = response.result
    assert result["ok"] is True
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_no_match"
    assert result["source_weak"] is True
    assert result["sources"] == []
    assert result["fetch_diagnostic"] is None


@pytest.mark.parametrize(
    "url_value",
    [
        None,
        "",
        "   ",
        42,
        True,
        ["https://bukgu.gwangju.kr/apply"],
        {"u": "https://bukgu.gwangju.kr/apply"},
    ],
)
def test_boundary_source_with_blank_or_non_string_url_returns_fallback(url_value):
    """Nonblank string url is required; blank/non-string drops the source."""
    def _boundary(plan):
        return {
            "ok": True,
            "answer_ok": True,
            "answer_markdown": "real answer",
            "sources": [{"id": "r1", "url": url_value}],
        }

    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )

    result = response.result
    assert result["ok"] is True
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_no_match"
    assert result["source_weak"] is True
    assert result["sources"] == []


# --- Fix #2: failure / non-strict-True ok must map to error, not fallback

@pytest.mark.parametrize(
    "ok_value",
    [
        False,
        "true",   # string, not bool
        1,        # int, not bool
        None,
        0,
        "",
        "false",
    ],
)
def test_boundary_non_strict_true_ok_returns_error_not_fallback(ok_value):
    """``ok`` must be strictly True; anything else -> safe error envelope.

    PR #816 review: a boundary that returns ``ok=False``, omits the
    key, or returns a non-bool truthy value (``"true"``, ``1``,
    ``None``) represents a transport-level failure. The runner must
    not silently relabel that as ``fallback_no_match``.
    """
    def _boundary(plan):
        return {
            "ok": ok_value,
            "answer_ok": True,
            "answer_markdown": "real answer",
            "sources": [{"id": "r1", "url": "https://bukgu.gwangju.kr/apply"}],
        }

    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )

    result = response.result
    assert result["ok"] is False
    assert result["answer_ok"] is False
    assert result["answer_status"] == "error"
    assert result["source_weak"] is True
    assert result["sources"] == []
    # Safe category-only diagnostic policy preserved.
    assert result["fetch_diagnostic"] is None


def test_boundary_ok_field_missing_returns_error_not_fallback():
    """A boundary dict with no ``ok`` key at all -> safe error."""
    def _boundary(plan):
        return {
            "answer_ok": True,
            "answer_markdown": "real answer",
            "sources": [{"id": "r1", "url": "https://bukgu.gwangju.kr/apply"}],
        }

    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )

    result = response.result
    assert result["ok"] is False
    assert result["answer_ok"] is False
    assert result["answer_status"] == "error"
    assert result["source_weak"] is True
    assert result["sources"] == []


def test_boundary_ok_false_with_safe_diagnostic_category_preserved():
    """Safe category-only diagnostic policy survives the error path."""
    def _boundary(plan):
        return {
            "ok": False,
            "answer_ok": True,
            "answer_markdown": "real answer",
            "sources": [{"id": "r1", "url": "https://bukgu.gwangju.kr/apply"}],
            "fetch_diagnostic": {
                "category": "connection_error",
                "message": "raw leak attempt",
                "headers": {"Authorization": "Bearer leak"},
            },
        }

    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )

    result = response.result
    assert result["ok"] is False
    assert result["answer_status"] == "error"
    # Only the safe category survives; message and headers are dropped.
    assert result["fetch_diagnostic"] == {"category": "connection_error"}


def test_boundary_timeout_exception_returns_fallback_unavailable():
    def _boundary(plan):
        raise TimeoutError("simulated pipeline timeout")
    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )
    result = response.result
    assert result["ok"] is False
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_unavailable"
    assert result["source_weak"] is True
    assert result["fetch_diagnostic"] == {"category": "timeout"}


@pytest.mark.parametrize("exc", [
    ConnectionError("simulated connection failure"),
    RuntimeError("simulated runtime failure"),
    ValueError("simulated value failure"),
])
def test_boundary_generic_exception_returns_error(exc):
    def _boundary(plan):
        raise exc
    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )
    result = response.result
    assert result["ok"] is False
    assert result["answer_ok"] is False
    assert result["answer_status"] == "error"
    assert result["source_weak"] is True
    assert result["fetch_diagnostic"] is None


@pytest.mark.parametrize("canary", SECRET_CANARIES)
def test_canary_in_boundary_exception_does_not_leak(canary):
    def _boundary(plan):
        raise RuntimeError(f"simulated failure with {canary}")
    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_boundary,
    )
    response_repr = repr(response)
    plan_repr = repr(response.plan)
    result_repr = repr(response.result)
    result_str = str(response.result)
    assert canary not in response_repr
    assert canary not in plan_repr
    assert canary not in result_repr
    assert canary not in result_str


def _make_canary_boundary(canary, placement):
    if placement == "title":
        sources = [{"id": "r1", "title": canary, "url": "https://bukgu.gwangju.kr/apply"}]
        diagnostic = None
    elif placement == "text":
        sources = [{"id": "r1", "text": canary, "url": "https://bukgu.gwangju.kr/apply"}]
        diagnostic = None
    elif placement == "url":
        sources = [{"id": "r1", "url": canary}]
        diagnostic = None
    elif placement == "fetch_diagnostic_message":
        sources = [{"id": "r1", "url": "https://bukgu.gwangju.kr/apply"}]
        diagnostic = {"category": "ok", "message": canary}
    elif placement == "fetch_diagnostic_headers":
        sources = [{"id": "r1", "url": "https://bukgu.gwangju.kr/apply"}]
        diagnostic = {"category": "ok", "headers": {"Authorization": canary}}
    else:
        raise ValueError(placement)

    def _boundary(plan):
        result = {
            "ok": True,
            "answer_ok": True,
            "answer_markdown": "real answer",
            "sources": sources,
        }
        if diagnostic is not None:
            result["fetch_diagnostic"] = diagnostic
        return result
    return _boundary


@pytest.mark.parametrize("canary, placement", [
    ("Bearer secret-token", "title"),
    ("Authorization: Bearer token-abc123", "fetch_diagnostic_message"),
    ("https://user:pass@example.test/path", "url"),
    ("header-like: x-api-key=abc123", "fetch_diagnostic_headers"),
    ("body-like secret=abc123", "text"),
])
def test_canary_in_boundary_return_value_does_not_leak(canary, placement):
    response = run_locked_controlled_live_ux(
        request=_opt_in_request(),
        execution_boundary=_make_canary_boundary(canary, placement),
    )
    response_repr = repr(response)
    plan_repr = repr(response.plan)
    result_repr = repr(response.result)
    result_str = str(response.result)
    assert canary not in response_repr
    assert canary not in plan_repr
    assert canary not in result_repr
    assert canary not in result_str
    for src in response.result["sources"]:
        assert canary not in repr(src)
        assert canary not in str(src)
    diag = response.result["fetch_diagnostic"]
    if diag is not None:
        assert canary not in repr(diag)
        assert canary not in str(diag)


@pytest.mark.parametrize("canary", SECRET_CANARIES)
def test_canary_question_does_not_leak_into_response_repr_or_result(canary):
    response = run_locked_controlled_live_ux(
        request=LockedControlledLiveUxRequest(
            question=canary,
            allow_controlled_live=True,
            acknowledgement=REQUIRED_ACKNOWLEDGEMENT,
        ),
    )
    response_repr = repr(response)
    plan_repr = repr(response.plan)
    result_repr = repr(response.result)
    result_str = str(response.result)
    assert canary not in response_repr
    assert canary not in plan_repr
    assert canary not in result_repr
    assert canary not in result_str


@pytest.mark.parametrize("canary", SECRET_CANARIES)
def test_canary_question_does_not_leak_into_exception_text(canary):
    long_canary = canary + "x" * (MAX_QUESTION_LEN + 1)
    with pytest.raises(LockedControlledLiveUxError) as exc_info:
        run_locked_controlled_live_ux(
            request=LockedControlledLiveUxRequest(question=long_canary),
        )
    assert canary not in str(exc_info.value)
    assert canary not in repr(exc_info.value)

    with pytest.raises(LockedControlledLiveUxError) as exc_info:
        run_locked_controlled_live_ux(
            request=LockedControlledLiveUxRequest(question=[canary]),
        )
    assert canary not in str(exc_info.value)
    assert canary not in repr(exc_info.value)


@pytest.mark.parametrize("question", [
    None, 42, True, False, "", "   ", "\n\t  ",
    "x" * (MAX_QUESTION_LEN + 1), ["a", "b"], {"question": "x"},
])
def test_invalid_question_raises_fixed_safe_code(question):
    with pytest.raises(LockedControlledLiveUxError) as exc_info:
        run_locked_controlled_live_ux(
            request=LockedControlledLiveUxRequest(question=question),
        )
    assert exc_info.value.code == QUESTION_INVALID_CODE
    assert str(exc_info.value) == QUESTION_INVALID_CODE
    assert QUESTION_INVALID_CODE in repr(exc_info.value)


def test_max_question_len_at_boundary_is_accepted():
    response = run_locked_controlled_live_ux(
        request=_request(question="가" * MAX_QUESTION_LEN),
    )
    assert response.mode == DRY_RUN_MODE
    assert response.execution_allowed is False


def test_max_question_len_plus_one_is_rejected():
    with pytest.raises(LockedControlledLiveUxError) as exc_info:
        run_locked_controlled_live_ux(
            request=_request(question="가" * (MAX_QUESTION_LEN + 1)),
        )
    assert exc_info.value.code == QUESTION_INVALID_CODE


def test_non_request_input_raises_invalid_request():
    with pytest.raises(LockedControlledLiveUxError) as exc_info:
        run_locked_controlled_live_ux(request="not a request")  # type: ignore[arg-type]
    assert exc_info.value.code == INVALID_REQUEST_CODE


def test_module_ast_has_no_forbidden_imports():
    path = Path(runner_module.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name)
                imported_names.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)
            imported_names.add(node.module.split(".", 1)[0])
    leaked = imported_names & FORBIDDEN_IMPORTS
    assert not leaked, f"Forbidden imports detected: {leaked}"


def test_import_is_pure():
    imported = importlib.import_module("src.demo.controlled_live_ux_runner")
    assert imported.run_locked_controlled_live_ux is run_locked_controlled_live_ux
    assert imported.LockedControlledLiveUxRequest is LockedControlledLiveUxRequest
    assert imported.LockedControlledLiveUxResponse is LockedControlledLiveUxResponse
    assert imported.LockedControlledLiveUxError is LockedControlledLiveUxError


def test_dry_run_does_not_call_network_or_process(monkeypatch):
    network_calls = []
    process_calls = []
    original_socket = socket.socket
    original_popen = subprocess.Popen

    def _tracking_socket(*args, **kwargs):
        network_calls.append("socket.socket")
        return original_socket(*args, **kwargs)

    def _tracking_popen(*args, **kwargs):
        process_calls.append("subprocess.Popen")
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(socket, "socket", _tracking_socket)
    monkeypatch.setattr(subprocess, "Popen", _tracking_popen)

    response = run_locked_controlled_live_ux(request=_request())
    assert response.mode == DRY_RUN_MODE
    assert network_calls == []
    assert process_calls == []


def test_module_exposes_required_symbols():
    assert hasattr(runner_module, "REQUIRED_ACKNOWLEDGEMENT")
    assert hasattr(runner_module, "DRY_RUN_MODE")
    assert hasattr(runner_module, "CONTROLLED_LIVE_REQUESTED_MODE")
    assert hasattr(runner_module, "MAX_QUESTION_LEN")
    assert hasattr(runner_module, "QUESTION_INVALID_CODE")
    assert hasattr(runner_module, "INVALID_REQUEST_CODE")
    assert hasattr(runner_module, "LockedControlledLiveUxError")
    assert hasattr(runner_module, "LockedControlledLiveUxRequest")
    assert hasattr(runner_module, "LockedControlledLiveUxResponse")
    assert hasattr(runner_module, "run_locked_controlled_live_ux")
