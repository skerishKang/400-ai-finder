"""Tests for the #925 Stage 1 MVP action-decision contract.

These tests exercise the model-backed action router and the decoupled
``/api/mvp/ask`` endpoint using **injectable fake providers** only. No real
model, API, fetch, crawler, Firecrawl, or live Buk-gu origin call is made.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from http.client import HTTPConnection

import pytest

from src.llm.base import LLMProvider, ProviderResult
from src.llm.bukgu_mvp_router import (
    MVP_FAILURE_ANSWER,
    MvpActionDecision,
    decide_mvp_action,
    is_mvp_failure,
    parse_mvp_decision,
)
from src.web.mobile_demo import create_app


# ----------------------------------------------------------------------
# Fake providers (no network, no real model)
# ----------------------------------------------------------------------

class _QuestionRoutedProvider(LLMProvider):
    """Returns a JSON MVP decision whose action depends on the question."""

    def __init__(self, answer_text: str = "안내입니다."):
        self._answer_text = answer_text

    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        question = ""
        for msg in messages:
            if msg.get("role") == "user":
                question = msg.get("content", "")
        if "주정차" in question or "불법" in question:
            action = "illegal_parking"
        elif "공동주택" in question or "아파트" in question:
            action = "housing_department"
        elif "전입신고" in question or "이사" in question:
            action = "move_in_report"
        elif "보건소" in question or "예방접종" in question:
            action = "public_health_center"
        else:
            action = "none"
        payload = {
            "answer": self._answer_text,
            "action": action,
            "confidence": 0.91,
        }
        return ProviderResult(
            ok=True,
            provider="fake",
            model="fake-model",
            content=json.dumps(payload, ensure_ascii=False),
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-model"


class _FailingProvider(LLMProvider):
    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        return ProviderResult(
            ok=False,
            provider="fake",
            model="fake-model",
            content="",
            error="injected provider failure",
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-model"


class _MalformedJsonProvider(LLMProvider):
    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        return ProviderResult(
            ok=True,
            provider="fake",
            model="fake-model",
            content="이것은 JSON이 아닙니다.",
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-model"


class _InvalidActionProvider(LLMProvider):
    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        payload = {"answer": "X", "action": "banana", "confidence": 0.5}
        return ProviderResult(
            ok=True,
            provider="fake",
            model="fake-model",
            content=json.dumps(payload, ensure_ascii=False),
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-model"


class _EmptyAnswerProvider(LLMProvider):
    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        payload = {"answer": "", "action": "illegal_parking", "confidence": 0.5}
        return ProviderResult(
            ok=True,
            provider="fake",
            model="fake-model",
            content=json.dumps(payload, ensure_ascii=False),
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-model"


class _RaisingProvider(LLMProvider):
    """Provider whose complete() raises — exercises exception absorption."""

    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        raise RuntimeError("injected provider exception")

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-model"


# ----------------------------------------------------------------------
# Parser / decision unit tests
# ----------------------------------------------------------------------

class TestMvpActionParser:
    def test_successful_parse(self):
        decision = parse_mvp_decision(
            json.dumps({"answer": "답변", "action": "illegal_parking", "confidence": 0.8})
        )
        assert decision.action == "illegal_parking"
        assert decision.answer == "답변"
        assert decision.confidence == 0.8

    def test_malformed_json_forced_none(self):
        decision = parse_mvp_decision("not json")
        assert decision.action == "none"
        assert decision.answer == MVP_FAILURE_ANSWER
        assert is_mvp_failure(decision)

    def test_invalid_action_forced_none(self):
        decision = parse_mvp_decision(
            json.dumps({"answer": "X", "action": "banana", "confidence": 0.5})
        )
        assert decision.action == "none"

    def test_empty_answer_forced_none(self):
        decision = parse_mvp_decision(
            json.dumps({"answer": "", "action": "illegal_parking", "confidence": 0.5})
        )
        assert decision.action == "none"

    def test_bad_confidence_clamped_to_zero(self):
        decision = parse_mvp_decision(
            json.dumps({"answer": "답변", "action": "none", "confidence": "high"})
        )
        assert decision.action == "none"
        assert decision.confidence == 0.0


class TestMvpActionDecision:
    def test_illegal_parking_variant(self):
        provider = _QuestionRoutedProvider()
        decision = decide_mvp_action("불법 주정차 신고는 어디서 하나요?", provider)
        assert decision.action == "illegal_parking"
        assert not is_mvp_failure(decision)

    def test_housing_department_variant(self):
        provider = _QuestionRoutedProvider()
        decision = decide_mvp_action("공동주택 과태료 문의하고 싶어요", provider)
        assert decision.action == "housing_department"
        assert not is_mvp_failure(decision)

    def test_none_variant(self):
        provider = _QuestionRoutedProvider()
        decision = decide_mvp_action("오늘 날씨 어떠세요?", provider)
        assert decision.action == "none"
        assert not is_mvp_failure(decision)

    def test_provider_failure_forced_none(self):
        decision = decide_mvp_action("anything", _FailingProvider())
        assert decision.action == "none"
        assert decision.answer == MVP_FAILURE_ANSWER
        assert is_mvp_failure(decision)

    def test_malformed_json_forced_none(self):
        decision = decide_mvp_action("anything", _MalformedJsonProvider())
        assert decision.action == "none"
        assert is_mvp_failure(decision)

    def test_invalid_action_forced_none(self):
        decision = decide_mvp_action("anything", _InvalidActionProvider())
        assert decision.action == "none"
        assert is_mvp_failure(decision)

    def test_empty_answer_forced_none(self):
        decision = decide_mvp_action("anything", _EmptyAnswerProvider())
        assert decision.action == "none"
        assert is_mvp_failure(decision)

    def test_provider_complete_exception_forced_none(self):
        decision = decide_mvp_action("anything", _RaisingProvider())
        assert decision.action == "none"
        assert decision.answer == MVP_FAILURE_ANSWER
        assert decision.confidence == 0.0
        assert is_mvp_failure(decision)


# ----------------------------------------------------------------------
# HTTP endpoint tests
# ----------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def mvp_server():
    port = _free_port()
    server = create_app(
        site_id="bukgu_gwangju",
        provider="mock",
        snapshot=None,
        host="127.0.0.1",
        port=port,
        mvp_provider=_QuestionRoutedProvider(),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


@pytest.fixture
def mvp_failure_server():
    port = _free_port()
    server = create_app(
        site_id="bukgu_gwangju",
        provider="mock",
        snapshot=None,
        host="127.0.0.1",
        port=port,
        mvp_provider=_FailingProvider(),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


class TestMvpAskEndpoint:
    def test_mvp_ask_illegal_parking(self, mvp_server):
        port = mvp_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "불법 주정차 신고 어디서 해요?"}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        assert resp.status == 200
        assert data["ok"] is True
        assert data["question"] == "불법 주정차 신고 어디서 해요?"
        assert data["action"] == "illegal_parking"
        assert "answer" in data and data["answer"]
        assert isinstance(data["confidence"], float)
        assert data["provider"] == "local_static"
        assert data["model"] == "quest-engine-v1"
        assert data["quest"]["quest_id"] == "illegal_parking_report_guidance"
        assert data["quest"]["source_mode"] == "local_static"
        assert data["action_plan"]["stop_condition"] == "STOP_FOR_USER_CONFIRMATION"
        assert data["action_plan"]["requires_user_confirmation"] is True
        assert data["action_plan"]["final_warning"]["requires_user_confirmation"] is True
        labels = [action["label"] for action in data["action_plan"]["browser_actions"]]
        assert "지도단속 안내 화면 이동" in labels
        assert "안전신문고 신고 경로 안내 확인" in labels

    def test_mvp_ask_housing_department(self, mvp_server):
        port = mvp_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "공동주택 문의 전화번호 알려줘"}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        assert resp.status == 200
        assert data["action"] == "housing_department"
        assert data["ok"] is True
        assert data["provider"] == "local_static"
        assert data["model"] == "quest-engine-v1"
        assert data["quest"]["quest_id"] == "housing_department_lookup"
        assert data["quest"]["source_mode"] == "local_static"
        assert data["action_plan"]["stop_condition"] == "STOP_AFTER_RESULT"
        labels = [action["label"] for action in data["action_plan"]["browser_actions"]]
        assert "업무 및 전화번호 안내 이동" in labels
        assert "공동주택 검색" in labels

    def test_mvp_ask_bulky_waste(self, mvp_server):
        port = mvp_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "침대 매트리스 버리고 싶어요"}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        assert resp.status == 200
        assert data["ok"] is True
        assert data["action"] == "bulky_waste"
        assert data["provider"] == "local_static"
        assert data["model"] == "quest-engine-v1"
        assert data["quest"]["quest_id"] == "bulky_waste_disposal_guidance"
        assert data["quest"]["source_mode"] == "local_static"
        assert data["action_plan"]["stop_condition"] == "STOP_FOR_USER_CONFIRMATION"
        assert data["action_plan"]["requires_user_confirmation"] is True
        assert data["action_plan"]["final_warning"]["requires_user_confirmation"] is True
        labels = [action["label"] for action in data["action_plan"]["browser_actions"]]
        assert "대형폐기물 배출방법 화면 이동" in labels
        assert "대형폐기물 배출방법 안내 확인" in labels

    def test_mvp_ask_public_health_center(self, mvp_server):
        port = mvp_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "보건소 어디에 있어요?"}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        assert resp.status == 200
        assert data["ok"] is True
        assert data["action"] == "public_health_center"
        assert data["provider"] == "local_static"
        assert data["model"] == "quest-engine-v1"
        assert data["quest"]["quest_id"] == "public_health_center_guidance"
        assert data["quest"]["source_mode"] == "local_static"
        assert data["action_plan"]["stop_condition"] == "STOP_FOR_USER_CONFIRMATION"
        assert data["action_plan"]["requires_user_confirmation"] is True
        assert data["action_plan"]["final_warning"]["requires_user_confirmation"] is True
        labels = [action["label"] for action in data["action_plan"]["browser_actions"]]
        assert "보건소 위치·진료 안내 화면 이동" in labels
        assert "보건소 위치·진료 안내 카드 확인" in labels

    def test_mvp_ask_move_in_report(self, mvp_server):
        port = mvp_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "이사 왔는데 전입신고는 어떻게 해요?"}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        assert resp.status == 200
        assert data["ok"] is True
        assert data["action"] == "move_in_report"
        assert data["provider"] == "local_static"
        assert data["model"] == "quest-engine-v1"
        assert data["quest"]["quest_id"] == "move_in_report_guidance"
        assert data["quest"]["source_mode"] == "local_static"
        assert data["action_plan"]["stop_condition"] == "STOP_FOR_USER_CONFIRMATION"
        assert data["action_plan"]["requires_user_confirmation"] is True
        assert data["action_plan"]["final_warning"]["requires_user_confirmation"] is True
        labels = [action["label"] for action in data["action_plan"]["browser_actions"]]
        assert "정부24 전입신고 연결 안내 화면 이동" in labels
        assert "정부24 전입신고 연결 안내 카드 확인" in labels

    def test_mvp_ask_none_unrelated(self, mvp_server):
        port = mvp_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "주말에 영화 뭐 있나요?"}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        assert resp.status == 200
        assert data["action"] == "none"
        assert data["ok"] is True

    def test_mvp_ask_empty_question_400(self, mvp_server):
        port = mvp_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": ""}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

    def test_mvp_ask_invalid_json_400(self, mvp_server):
        port = mvp_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", "/api/mvp/ask", body=b"not json",
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

    def test_mvp_ask_provider_failure_contract(self, mvp_failure_server):
        port = mvp_failure_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "오늘 북구 날씨 알려줘"}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        assert resp.status == 200
        assert data["ok"] is False
        assert data["action"] == "none"
        assert data["answer"] == MVP_FAILURE_ANSWER


class TestMvpActionConfidenceNormalization:
    def _decision_for_confidence(self, raw_confidence):
        payload = {
            "answer": "정상 답변",
            "action": "none",
            "confidence": raw_confidence,
        }
        return parse_mvp_decision(json.dumps(payload, ensure_ascii=False))

    def test_none_confidence_clamped_to_zero(self):
        assert self._decision_for_confidence(None).confidence == 0.0

    def test_nan_string_clamped_to_zero(self):
        assert self._decision_for_confidence("NaN").confidence == 0.0

    def test_infinity_clamped_to_zero(self):
        assert self._decision_for_confidence("Infinity").confidence == 0.0

    def test_negative_infinity_clamped_to_zero(self):
        assert self._decision_for_confidence("-Infinity").confidence == 0.0

    def test_nonnumeric_string_clamped_to_zero(self):
        assert self._decision_for_confidence("high").confidence == 0.0

    def test_negative_clamped_to_zero(self):
        assert self._decision_for_confidence(-0.5).confidence == 0.0

    def test_over_one_clamped_to_one(self):
        assert self._decision_for_confidence(1.5).confidence == 1.0

    def test_valid_confidence_preserved(self):
        assert self._decision_for_confidence(0.73).confidence == 0.73

    def test_nan_float_clamped_to_zero(self):
        assert self._decision_for_confidence(float("nan")).confidence == 0.0

    def test_inf_float_clamped_to_zero(self):
        assert self._decision_for_confidence(float("inf")).confidence == 0.0

    def test_valid_answer_action_not_failed_by_confidence(self):
        d = self._decision_for_confidence(0.0)
        assert d.action == "none"
        assert not is_mvp_failure(d)


@pytest.fixture
def mvp_provider_resolution_error_server():
    """Server whose configured provider triggers a get_provider() failure."""
    port = _free_port()
    server = create_app(
        site_id="bukgu_gwangju",
        provider="opencode-go",  # pending-config provider → get_provider raises
        snapshot=None,
        host="127.0.0.1",
        port=port,
        mvp_provider=None,  # force the get_provider() path
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


class TestMvpAskProviderResolutionFailure:
    def test_get_provider_exception_returns_stable_200(self, mvp_provider_resolution_error_server):
        port = mvp_provider_resolution_error_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "오늘 북구 날씨 알려줘"}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        assert resp.status == 200
        assert data["ok"] is False
        assert data["question"] == "오늘 북구 날씨 알려줘"
        assert data["answer"] == MVP_FAILURE_ANSWER
        assert data["action"] == "none"
        assert data["confidence"] == 0.0
        assert data["provider"] == "opencode-go"
        assert data["model"] == ""
