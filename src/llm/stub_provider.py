"""Stub provider — simulates a real LLM grounded answer for testing.

The stub provider reads the source context from the messages and generates
a realistic grounded answer WITHOUT making any API calls. This allows:

1. Testing the full pipeline end-to-end without API keys
2. Verifying that sources are properly passed to the LLM
3. Confirming the answer references the actual source data
4. Testing hallucination prevention (sources not present → "not found")

Usage::

    from src.llm import StubProvider
    provider = StubProvider()
    result = provider.complete(messages)
"""

from __future__ import annotations

import re
from typing import Any

from .base import LLMProvider, ProviderResult


class StubProvider(LLMProvider):
    """Provider that generates source-grounded answers without API calls.

    Parses the source context from the user message and produces
    a Markdown answer that references actual source titles and URLs.
    """

    def __init__(self, fail_on: str | None = None):
        """
        Args:
            fail_on: If set, returns ok=False when a source title contains this string.
                     Used to test error handling paths.
        """
        self._fail_on = fail_on

    def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout: int = 60,
    ) -> ProviderResult:
        user_msg = next(
            (m["content"] for m in messages if m["role"] == "user"), ""
        )
        query = self._extract_query(user_msg)
        sources = self._parse_sources(user_msg)

        if not sources:
            return self._no_sources_result()

        # Check for forced failure test
        if self._fail_on:
            for s in sources:
                if self._fail_on.lower() in s["title"].lower():
                    return ProviderResult(
                        ok=False,
                        provider=self.provider_name,
                        model=self.model_name,
                        content="",
                        error=f"Simulated failure triggered by source: {s['title']}",
                    )

        answer = self._build_answer(query, sources)
        return ProviderResult(
            ok=True,
            provider=self.provider_name,
            model=self.model_name,
            content=answer,
            raw={"sources_count": len(sources), "query": query},
        )

    @staticmethod
    def _extract_query(user_msg: str) -> str:
        """Extract the user's question from the message."""
        match = re.search(
            r"## 사용자 질문\s*\n\s*\n(.+?)\s*\n\s*## Source Context",
            user_msg,
            re.DOTALL,
        )
        if match:
            return match.group(1).strip()
        # Fallback: first non-empty line after "사용자 질문"
        lines = user_msg.split("\n")
        for i, line in enumerate(lines):
            if "사용자 질문" in line and i + 1 < len(lines):
                return lines[i + 1].strip()
        return "알 수 없는 질문"

    @staticmethod
    def _parse_sources(user_msg: str) -> list[dict[str, str]]:
        """Parse [Source N] blocks from the source context."""
        sources = []
        # Find each [Source N] block
        blocks = re.split(r"\[Source (\d+)\]", user_msg)
        # blocks[0] is content before first [Source]
        # blocks[1] is the number, blocks[2] is the block content, etc.
        for i in range(1, len(blocks) - 1, 2):
            num = blocks[i]
            content = blocks[i + 1]
            src = {
                "rank": num,
                "title": "",
                "url": "",
                "category": "",
                "snippet": "",
            }
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("title:"):
                    src["title"] = line[len("title:"):].strip()
                elif line.startswith("url:"):
                    src["url"] = line[len("url:"):].strip()
                elif line.startswith("category:"):
                    src["category"] = line[len("category:"):].strip()
                elif line.startswith("snippet:"):
                    src["snippet"] = line[len("snippet:"):].strip()
                elif line.startswith("description:"):
                    desc = line[len("description:"):].strip()
                    if desc and not src["snippet"]:
                        src["snippet"] = desc
            if src["title"]:
                sources.append(src)
        return sources

    @staticmethod
    def _build_answer(query: str, sources: list[dict[str, str]]) -> str:
        """Build a grounded Markdown answer from sources."""
        # Find best source
        best = sources[0]
        best_title = best.get("title", "관련 페이지")
        best_url = best.get("url", "")

        q_tokens = set(query.lower().split())
        matching = [s for s in sources if any(
            t in s.get("title", "").lower() for t in q_tokens
        )]
        primary = matching[0] if matching else best

        title = primary.get("title", "관련 페이지")
        url = primary.get("url", "")
        snippet = primary.get("snippet", "")

        lines = ["## 답변\n"]
        lines.append(
            f"'{title}' 관련 정보를 찾았습니다.\n"
        )
        if snippet:
            lines.append(f"{snippet}\n")

        lines.append("\n## 관련 자료\n")
        lines.append(f"- [{title}]({url})")
        for s in sources[1:3]:
            t = s.get("title", "")
            u = s.get("url", "")
            if t and u and (t, u) != (title, url):
                lines.append(f"- [{t}]({u})")

        lines.append(
            "\n## 다음 단계\n\n"
            "1. 위 링크를 클릭하여 해당 페이지로 이동합니다.\n"
            "2. 필요한 서류와 절차를 확인합니다.\n"
        )
        lines.append(
            "\n## 확인 필요\n\n"
            "정확한 최신 내용은 연결된 공식 홈페이지에서 확인해 주세요.\n"
        )
        return "\n".join(lines)

    @staticmethod
    def _no_sources_result() -> ProviderResult:
        answer = (
            "## 답변\n\n"
            "관련 자료를 찾지 못했습니다.\n\n"
            "## 다음 단계\n\n"
            "검색어를 바꾸거나 홈페이지 원문을 다시 확인해야 합니다.\n\n"
            "## 확인 필요\n\n"
            "정확한 최신 내용은 연결된 공식 홈페이지에서 확인해 주세요.\n"
        )
        return ProviderResult(
            ok=True,
            provider="stub",
            model="stub",
            content=answer,
        )

    @property
    def provider_name(self) -> str:
        return "stub"

    @property
    def model_name(self) -> str:
        return "stub"
