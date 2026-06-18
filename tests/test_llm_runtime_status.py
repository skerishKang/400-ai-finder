"""No-live tests for LLM runtime status classification."""

from __future__ import annotations

from src.llm.runtime_status import (
    is_live_llm_provider,
    resolve_llm_runtime_status,
)


def test_mock_is_not_live() -> None:
    status = resolve_llm_runtime_status("mock", model="mock", ok=True)
    assert status == {
        "llm_live": False,
        "llm_status": "mock_no_api",
        "llm_label": "mock — 테스트 고정 응답",
    }


def test_stub_is_not_live() -> None:
    status = resolve_llm_runtime_status("stub", model="stub", ok=True)
    assert status == {
        "llm_live": False,
        "llm_status": "stub_no_api",
        "llm_label": "stub — source 기반 시뮬레이션, 외부 LLM API 미사용",
    }


def test_live_provider_success_is_live() -> None:
    status = resolve_llm_runtime_status(
        "nvidia",
        model="stepfun-ai/step-3.7-flash",
        ok=True,
        answer_ok=True,
    )
    assert status["llm_live"] is True
    assert status["llm_status"] == "live_provider_configured"
    assert "실제 LLM 연결" in status["llm_label"]


def test_snapshot_mode_is_not_live() -> None:
    status = resolve_llm_runtime_status("nvidia", model="stepfun-ai/step-3.7-flash", snapshot_mode=True)
    assert status == {
        "llm_live": False,
        "llm_status": "snapshot_no_api",
        "llm_label": "snapshot — 저장된 source 자료 기반, 외부 LLM API 미사용",
    }


def test_live_provider_not_called_is_not_live() -> None:
    status = resolve_llm_runtime_status("nvidia", model="stepfun-ai/step-3.7-flash")
    assert status["llm_live"] is False
    assert status["llm_status"] == "live_provider_not_called"


def test_live_provider_config_error_is_not_live() -> None:
    status = resolve_llm_runtime_status(
        "nvidia",
        model="stepfun-ai/step-3.7-flash",
        ok=False,
        warnings=["LLM API key is not configured."],
    )
    assert status["llm_live"] is False
    assert status["llm_status"] == "live_provider_not_configured"


def test_unknown_provider_is_not_live() -> None:
    status = resolve_llm_runtime_status("unknown", model="x")
    assert status["llm_live"] is False
    assert status["llm_status"] == "unknown_provider"


def test_is_live_llm_provider() -> None:
    assert is_live_llm_provider("nvidia") is True
    assert is_live_llm_provider("NVIDIA") is True
    assert is_live_llm_provider("stub") is False
