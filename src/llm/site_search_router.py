"""LLM-first positive site-search router.

Routes user questions to one of three routes using LLM classification:

- ``site_search``:   user question likely maps to a real search on the site
- ``direct_answer``: no search is required (e.g. greetings, how-to-use questions)
- ``clarify``:       user question is too short or too ambiguous to search

Design principles:

- LLM classification is primary; no keyword/rule-based smalltalk blocker.
- Default bias is **positive**: when the LLM is unavailable, returns or returns
  an unparseable payload, the fallback is ``site_search`` so the system
  errs on the side of searching.
- The router is decoupled from PipelineRunner so tests can inject a mock
  LLM provider and assert on the decision in isolation.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Optional

log = logging.getLogger(__name__)


VALID_ROUTES = ("site_search", "direct_answer", "clarify")


@dataclass
class RouterDecision:
    route: str
    should_search_site: bool
    confidence: float
    reason: str
    search_query: str
    direct_answer: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_prompt(question: str, site_name: str) -> str:
    site = (site_name or "").strip() or "해당 기관"
    q = (question or "").strip()
    return (
        "당신은 '" + site + "' 홈페이지 정보를 안내하는 AI 라우터입니다.\n"
        "\n"
        "사용자 발화가 '" + site + "' 정보 탐색으로 이어질 가능성이 있으면 site_search로, "
        "명백히 검색이 필요 없는 인사/도움말이면 direct_answer로, "
        "너무 짧아서 검색 대상을 정할 수 없으면 clarify로 판단하세요.\n"
        "\n"
        "기본 방향: '" + site + "' 관련 가능성이 있으면 적극적으로 site_search로 보내세요. "
        "검색 실패를 피하려고 막지 말고, 검색해야 할 질문을 더 잘 찾아내는 게 목표입니다.\n"
        "\n"
        "출력은 반드시 다음 JSON 형식만 사용하세요 (다른 텍스트 없이):\n"
        "{\n"
        '  "route": "site_search|direct_answer|clarify",\n'
        '  "should_search_site": true|false,\n'
        '  "confidence": 0.0~1.0,\n'
        '  "reason": "판단 이유 한 줄",\n'
        '  "search_query": "site_search일 때 검색할 자연어 질문 (없으면 원문)",\n'
        '  "direct_answer": "direct_answer 또는 clarify일 때 사용자에게 보여줄 안내 문구"\n'
        "}\n"
        "\n"
        "사용자 발화: \"" + q + "\"\n"
    )


def _parse_decision(text: str, fallback_question: str) -> Optional[RouterDecision]:
    if not text:
        return None
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    route = str(data.get("route", "")).strip().lower()
    if route not in VALID_ROUTES:
        return None
    try:
        confidence = float(data.get("confidence", 0.0))
    except Exception:
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    return RouterDecision(
        route=route,
        should_search_site=bool(data.get("should_search_site", route == "site_search")),
        confidence=confidence,
        reason=str(data.get("reason", "")).strip(),
        search_query=str(data.get("search_query", "")).strip(),
        direct_answer=str(data.get("direct_answer", "")).strip(),
    )


def default_fallback_decision(question: str, site_name: str) -> RouterDecision:
    """Positive fallback used when the LLM call fails or returns garbage.

    Bias: err on the side of ``site_search`` so the pipeline still tries to
    answer the user instead of returning a hard block.
    """
    cleaned = (question or "").strip()
    return RouterDecision(
        route="site_search",
        should_search_site=True,
        confidence=0.0,
        reason="router_fallback_positive",
        search_query=cleaned or f"{(site_name or '해당 기관')} 안내",
        direct_answer="",
    )


def greeting_fallback_direct_answer(site_name: str) -> str:
    """Used when route == 'direct_answer' and the LLM did not supply one."""
    site = (site_name or "").strip() or "해당 기관"
    return (
        "안녕하세요. " + site + " 민원, 공고, 복지, 부서, 신청·신고 정보를 "
        "찾아드릴 수 있어요. 궁금한 내용을 편하게 물어보세요."
    )


def clarify_fallback_direct_answer(site_name: str) -> str:
    site = (site_name or "").strip() or "해당 기관"
    return (
        "어떤 내용을 찾아드릴지 조금만 알려주시면 바로 " + site + " 자료에서 "
        "찾아볼게요."
    )


class SiteSearchRouter:
    """LLM-first site-search router.

    Tests can pass a mock ``provider`` whose ``.generate`` returns a
    ``ProviderResult`` with a ``text`` field. In production, an
    ``OpenAICompatibleProvider`` is used and the decision is produced by
    the configured LLM.
    """

    def __init__(self, provider: Any = None, model: Optional[str] = None, site_name: str = "") -> None:
        self.provider = provider
        self.model = model
        self.site_name = site_name

    def decide(self, question: str) -> RouterDecision:
        if not self.provider:
            return default_fallback_decision(question, self.site_name)
        prompt = _build_prompt(question or "", self.site_name)
        try:
            result = self.provider.generate(prompt=prompt, model=self.model or "")
        except Exception as e:  # noqa: BLE001 - never break the user response
            log.debug("router LLM call failed: %s", e)
            return default_fallback_decision(question, self.site_name)
        text = getattr(result, "text", "") or ""
        decision = _parse_decision(text, question or "")
        if not decision:
            return default_fallback_decision(question, self.site_name)
        if decision.route == "site_search":
            decision.should_search_site = True
            if not decision.search_query:
                decision.search_query = (question or "").strip()
        elif decision.route in ("direct_answer", "clarify"):
            decision.should_search_site = False
        return decision
