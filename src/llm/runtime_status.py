"""LLM runtime status helpers for demo and operator UI responses.

The helper intentionally classifies only the runtime mode. It does not inspect
secrets and never prints or stores API keys.
"""

from __future__ import annotations

from typing import Any

LIVE_PROVIDERS = {
    "openai_compatible",
    "mistral",
    "opengateway",
    "kilocode",
    "nvidia",
    "groq",
    "opencode-go",
    "opencode-zen",
    "nous",
}

_NO_API_STATUSES = {
    "mock": {
        "llm_live": False,
        "llm_status": "mock_no_api",
        "llm_label": "mock — 테스트 고정 응답",
    },
    "stub": {
        "llm_live": False,
        "llm_status": "stub_no_api",
        "llm_label": "stub — source 기반 시뮬레이션, 외부 LLM API 미사용",
    },
    "snapshot": {
        "llm_live": False,
        "llm_status": "snapshot_no_api",
        "llm_label": "snapshot — 저장된 source 자료 기반, 외부 LLM API 미사용",
    },
}


def is_live_llm_provider(provider: str | None) -> bool:
    """Return True when provider is a real LLM provider family."""
    return (provider or "").strip().lower() in LIVE_PROVIDERS


def resolve_llm_runtime_status(
    provider: str,
    model: str | None = None,
    ok: bool | None = None,
    answer_ok: bool | None = None,
    warnings: list[str] | None = None,
    snapshot_mode: bool = False,
) -> dict[str, Any]:
    """Resolve demo/operator-visible LLM runtime status.

    Status rules:
    - mock: no API, fixed test response.
    - stub: no API, source-based simulated answer.
    - snapshot_mode: no API, stored source data answer.
    - live provider + successful answer: live_provider_configured.
    - live provider before first call: live_provider_not_called.
    - live provider + configuration/call failure: live_provider_not_configured or live_provider_error.
    """
    normalized_provider = (provider or "").strip().lower()
    warning_text = "\n".join(warnings or []).lower()

    if snapshot_mode:
        return dict(_NO_API_STATUSES["snapshot"])

    if normalized_provider in _NO_API_STATUSES:
        return dict(_NO_API_STATUSES[normalized_provider])

    if not is_live_llm_provider(normalized_provider):
        return {
            "llm_live": False,
            "llm_status": "unknown_provider",
            "llm_label": f"{normalized_provider or 'unknown'} — 알 수 없는 LLM provider",
        }

    effective_answer_ok = answer_ok if answer_ok is not None else ok
    if effective_answer_ok is None:
        return {
            "llm_live": False,
            "llm_status": "live_provider_not_called",
            "llm_label": f"{normalized_provider} — 설정 여부 미확인, 아직 호출 없음",
        }

    if effective_answer_ok is True:
        model_part = f" ({model})" if model else ""
        return {
            "llm_live": True,
            "llm_status": "live_provider_configured",
            "llm_label": f"{normalized_provider} — 실제 LLM 연결{model_part}",
        }

    if "api key" in warning_text or "base url" in warning_text or "not configured" in warning_text:
        return {
            "llm_live": False,
            "llm_status": "live_provider_not_configured",
            "llm_label": f"{normalized_provider} — 설정 또는 호출 실패",
        }

    return {
        "llm_live": False,
        "llm_status": "live_provider_error",
        "llm_label": f"{normalized_provider} — 설정 또는 호출 실패",
    }


__all__ = [
    "LIVE_PROVIDERS",
    "is_live_llm_provider",
    "resolve_llm_runtime_status",
]
