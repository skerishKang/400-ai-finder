"""Tests for Stage 30 exception hardening and pending configuration handling."""

from __future__ import annotations
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from src.demo import SiteDemoRunner
from src.llm import resolve_provider_model, get_provider
from src.web.mobile_demo import create_app
from src.web.admin_demo import create_admin_app

def test_resolve_default_deepseek_metadata():
    """Verify resolve_provider_model resolves to DeepSeek primary preset by default."""
    provider, model = resolve_provider_model(None, None, None)
    assert provider == "opencode-go"
    assert model == "deepseek-v4-flash"


def test_pending_provider_graceful_error_handling(tmp_path):
    """Verify that when a provider is pending configuration, answer() handles it gracefully without live fetch."""
    # Ensure environment is clean (no opencode keys)
    with patch.dict(os.environ, {}, clear=True):
        p, m = resolve_provider_model(None, None, None)
        assert p == "opencode-go"

        # Pre-create a dummy homepage-map.json in output_dir so fallback match succeeds
        dummy_map = {
            "homepage": {
                "navigation_links": [
                    {"title": "민원서식", "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000"}
                ]
            },
            "categories": {
                "menu": []
            }
        }
        os.makedirs(tmp_path, exist_ok=True)
        with open(os.path.join(tmp_path, "homepage-map.json"), "w", encoding="utf-8") as f:
            json.dump(dummy_map, f)

        # Mock PipelineRunner.run to raise ValueError (simulate pending provider logic)
        with patch("src.pipeline.pipeline_runner.PipelineRunner.run") as mock_run:
            mock_run.side_effect = ValueError("Provider 'opencode-go' is pending configuration.")

            # Create runner with the pending provider
            runner = SiteDemoRunner(
                site_id="bukgu_gwangju",
                provider=p,
                model=m,
                output_dir=str(tmp_path),
            )

            # Running answer should not raise ValueError, but return a graceful fallback response
            # with fallback sources maintained (e.g. from homepage-map menu candidates)
            result = runner.answer("민원서식 어디서 받아?")
            assert result["ok"] is False
            assert result["answer_ok"] is False
            # PR #799: when the pipeline raises, the runner now surfaces a
            # pipeline_warning which switches the soft fallback to the
            # "공식 홈페이지 응답이 지연" message instead of the generic hint.
            assert "공식 홈페이지 응답이 지연" in result["answer"]
            assert len(result["sources"]) > 0  # Fallback sources should be preserved
            # Stage #800: the warning carries the sanitized diagnostic
            # category instead of the raw exception message. Operators
            # still see *why* the pipeline failed (timeout vs.
            # unknown), but the raw "pending configuration" string never
            # appears in operator-facing output.
            assert any("category=" in w for w in result["warnings"])
            assert any("category=unknown_fetch_error" in w for w in result["warnings"])


def test_mobile_demo_graceful_ask_error():
    """Verify mobile_demo API ask endpoint handles LLM exceptions gracefully."""
    # Instantiate handler mock-style to test _handle_ask
    from src.web.mobile_demo import MobileDemoHandler

    # Make mock runner that raises ValueError (simulate pending provider)
    runner_mock = MagicMock()
    runner_mock.answer.side_effect = ValueError("opencode-go pending configuration mock error")

    # Let's mock handler dependencies and inject runner_mock directly
    handler = MagicMock(spec=MobileDemoHandler)
    handler.site_id = "bukgu_gwangju"
    handler.provider = "opencode-go"
    handler.model = "deepseek-v4-flash"
    handler.snapshot_path = None
    handler._runner = runner_mock
    handler._site_name = "광주광역시 북구청"

    # Trigger actual method logic with clean env
    with patch.dict(os.environ, {}, clear=True):
        # We mock the http request parser and json_response
        handler.headers = {"Content-Length": "37"}
        handler.rfile = MagicMock()
        handler.rfile.read.return_value = '{"question": "민원서식"}'.encode('utf-8')
        
        response_data = None
        def mock_json_response(data, status=200):
            nonlocal response_data
            response_data = data
        handler._json_response = mock_json_response

        # Run handle_ask code
        MobileDemoHandler._handle_ask(handler)

        assert response_data is not None
        assert response_data["ok"] is False
        assert "제가 확인한 자료 기준으로는 관련 메뉴가 가장 먼저 필요해 보입니다" in response_data["answer"]
        assert response_data["provider"] == "opencode-go"
        assert "pending configuration mock error" in response_data["warnings"][0]


def test_admin_demo_graceful_test_error():
    """Verify admin_demo API test endpoint handles LLM exceptions gracefully."""
    from src.web.admin_demo import AdminDemoHandler

    # Make mock runner that raises ValueError (simulate pending provider)
    runner_mock = MagicMock()
    runner_mock.answer.side_effect = ValueError("opencode-go mock pending configuration error")
    runner_mock.answer_from_snapshot.side_effect = ValueError("opencode-go mock pending configuration error")

    handler = MagicMock(spec=AdminDemoHandler)
    handler.site_id = "bukgu_gwangju"
    handler.provider = "opencode-go"
    handler.model = "deepseek-v4-flash"
    handler.snapshot_path = None
    handler._runner_cache = {("bukgu_gwangju", "opencode-go", "deepseek-v4-flash"): runner_mock}
    handler._site_name = "광주광역시 북구청"

    with patch.dict(os.environ, {}, clear=True):
        handler.headers = {"Content-Length": "37"}
        handler.rfile = MagicMock()
        handler.rfile.read.return_value = '{"question": "민원서식"}'.encode('utf-8')
        
        response_data = None
        def mock_json_response(data, status=200):
            nonlocal response_data
            response_data = data
        handler._json_response = mock_json_response

        AdminDemoHandler._handle_test(handler)

        assert response_data is not None
        assert response_data["ok"] is False
        assert response_data["answer_ok"] is False
        assert response_data["provider"] == "opencode-go"
        assert response_data["model"] == "deepseek-v4-flash"
        assert response_data["preset"] == "deepseek-primary"
        assert "mock pending configuration error" in response_data["error"]


def test_timeout_hardening(tmp_path):
    """Verify timeout exception in PipelineRunner.run does not crash runner and keeps sources."""
    # Pre-create dummy map
    dummy_map = {
        "homepage": {
            "navigation_links": [
                {"title": "민원서식", "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000"}
            ]
        },
        "categories": {
            "menu": []
        }
    }
    os.makedirs(tmp_path, exist_ok=True)
    with open(os.path.join(tmp_path, "homepage-map.json"), "w", encoding="utf-8") as f:
        json.dump(dummy_map, f)

    # We mock runner.run to raise a timeout exception
    with patch("src.pipeline.pipeline_runner.PipelineRunner.run") as mock_run:
        mock_run.side_effect = TimeoutError("LLM API Call Timeout")

        runner = SiteDemoRunner(
            site_id="bukgu_gwangju",
            provider="mock",
            output_dir=str(tmp_path),
        )

        result = runner.answer("민원서식 어디서 받아?")
        assert result["ok"] is False
        assert result["answer_ok"] is False
        # PR #799: a raised TimeoutError inside the pipeline surfaces as a
        # pipeline_warning and selects the "공식 홈페이지 응답이 지연"
        # soft-fallback message.
        assert "공식 홈페이지 응답이 지연" in result["answer"]
        assert len(result["sources"]) > 0  # Sources from fallback menu matching should be kept
        # Stage #800: PR #799 preserves the original exception message
        # here for diagnostic value, but Stage #800 routes it through
        # the seven-category taxonomy so the operator-facing warning is
        # closed-vocabulary only. We assert the diagnostic category is
        # present; the raw "LLM API Call Timeout" string is intentionally
        # no longer echoed in operator-facing output.
        assert any("category=" in w for w in result["warnings"])
        assert any("category=timeout" in w for w in result["warnings"])


def test_mimo_step_override_regression():
    """Verify MiMo and Step overrides still resolve properly."""
    # 1. mimo preset override
    p1, m1 = resolve_provider_model(None, None, "mimo-primary")
    assert p1 == "opengateway"
    assert m1 == "mimo-v2.5-pro"

    # 2. mimo model-provider override
    p2, m2 = resolve_provider_model("mimo-v2.5-pro", "opengateway", None)
    assert p2 == "opengateway"
    assert m2 == "mimo-v2.5-pro"

    # 3. step model-provider override
    p3, m3 = resolve_provider_model("stepfun-ai/step-3.5-flash", "nvidia", None)
    assert p3 == "nvidia"
    assert m3 == "stepfun-ai/step-3.5-flash"


def test_admin_demo_dynamic_payload_resolution():
    """Verify admin_demo test API dynamically resolves preset, model, and provider from POST request payload."""
    from src.web.admin_demo import AdminDemoHandler

    handler = MagicMock(spec=AdminDemoHandler)
    handler.site_id = "bukgu_gwangju"
    handler.provider = "mock"
    handler.model = "mock"
    handler.snapshot_path = None
    # PR #799: ``AdminDemoHandler`` reads ``self.pipeline_timeout_s`` when
    # constructing the runner. Explicitly pin it to ``None`` (the class
    # default) so the MagicMock doesn't leak into the runner factory.
    handler.pipeline_timeout_s = None
    handler._runner_cache = {}  # empty cache — forces new runner creation
    handler._site_name = "광주광역시 북구청"

    # Mock SiteDemoRunner response to check what was passed
    runner_mock = MagicMock()
    runner_mock.answer.return_value = {
        "site_id": "bukgu_gwangju",
        "site_name": "광주광역시 북구청",
        "question": "민원서식",
        "answer": "정상 답변",
        "sources": [],
        "search_results": [],
        "ok": True,
        "answer_ok": True,
        "provider": "opengateway",
        "model": "mimo-v2.5-pro",
    }
    # Also mock answer_from_snapshot (used when fixture file auto-resolves)
    runner_mock.answer_from_snapshot.return_value = runner_mock.answer.return_value

    # Inject mock runner during init
    with patch("src.demo.SiteDemoRunner", return_value=runner_mock) as mock_runner_cls:
        handler.headers = {"Content-Length": "120"}
        handler.rfile = MagicMock()
        # Requesting mimo-primary preset
        handler.rfile.read.return_value = json.dumps({
            "question": "민원서식",
            "preset": "mimo-primary",
            "model": "mimo-v2.5-pro",
            "provider": "opengateway"
        }).encode('utf-8')

        response_data = None
        def mock_json_response(data, status=200):
            nonlocal response_data
            response_data = data
        handler._json_response = mock_json_response

        # Execute
        AdminDemoHandler._handle_test(handler)

        # Check mock instantiation params
        mock_runner_cls.assert_called_once_with(
            site_id="bukgu_gwangju",
            provider="opengateway",
            model="mimo-v2.5-pro",
            pipeline_timeout_s=None,
        )
        assert response_data is not None
        assert response_data["provider"] == "opengateway"
        assert response_data["model"] == "mimo-v2.5-pro"
        assert response_data["preset"] == "mimo-primary"
