"""Stage 368 — site_id-aware offline retrieval evidence for the first
bukgu_gwangju synonym dictionary slice.

Verifies that with ``site_id="bukgu_gwangju"`` passed to
``rewrite_query_candidates()``, an offline ``KeywordSearcher`` index
can actually surface documents whose text only contains the
approved menu vocabulary (종합민원 / 민원서식 / 고시공고 / 교육접수
/ 열린구청장실).

This is an end-to-end evidence step on top of:
- Stage 363 synonym_dictionary contract
- Stage 365 first bukgu_gwangju slice
- Stage 366 rewrite-output audit

The test directly drives ``KeywordSearcher.search`` over the
``rewrite_query_candidates`` output (mirroring
``PipelineRunner._search_for_candidates``) so it does not depend on
the pipeline_runner plumbing currently not forwarding ``site_id``.

No live calls. No provider. No LLM. No Firecrawl. No new synonym
data. Stable menu vocabulary only — no person names, officeholder
names, volatile facts, or answer sentences.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.search.query_rewriter import rewrite_query_candidates
from src.search.keyword_searcher import KeywordSearcher


# ------------------------------------------------------------------
# Synthetic offline enriched index
# ------------------------------------------------------------------

DOCS: list[dict] = [
    {
        "id": "minwon-jonghap",
        "title": "종합민원 안내",
        "url": "https://bukgu.gwangju.kr/minwon/jonghap",
        "canonical_url": "https://bukgu.gwangju.kr/minwon/jonghap",
        "category": "menu",
        "content_type": "page",
        "score": 0.0,
        "text": "종합민원 온라인 민원 민원서식 발급",
        "summary": "종합민원 안내 페이지",
        "metadata": {
            "link_texts": ["종합민원", "온라인 민원"],
            "fetch_status": "fetched",
        },
    },
    {
        "id": "minwon-seosik",
        "title": "민원서식 다운로드",
        "url": "https://bukgu.gwangju.kr/minwon/seosik",
        "canonical_url": "https://bukgu.gwangju.kr/minwon/seosik",
        "category": "document",
        "content_type": "page",
        "score": 0.0,
        "text": "민원서식 작성예시 QR코드",
        "summary": "민원서식 안내 페이지",
        "metadata": {
            "link_texts": ["민원서식"],
            "fetch_status": "fetched",
        },
    },
    {
        "id": "gosi-gonggo",
        "title": "고시공고",
        "url": "https://bukgu.gwangju.kr/board/gonggo",
        "canonical_url": "https://bukgu.gwangju.kr/board/gonggo",
        "category": "board",
        "content_type": "page",
        "score": 0.0,
        "text": "고시공고 공지사항 새소식 입법예고",
        "summary": "고시공고 목록",
        "metadata": {
            "link_texts": ["고시공고", "공지사항", "새소식"],
            "fetch_status": "fetched",
        },
    },
    {
        "id": "education-jeopsu",
        "title": "교육접수 안내",
        "url": "https://bukgu.gwangju.kr/education/jeopsu",
        "canonical_url": "https://bukgu.gwangju.kr/education/jeopsu",
        "category": "menu",
        "content_type": "page",
        "score": 0.0,
        "text": "교육접수 평생교육 강좌 프로그램",
        "summary": "교육접수 안내 페이지",
        "metadata": {
            "link_texts": ["교육접수", "평생교육", "강좌", "프로그램"],
            "fetch_status": "fetched",
        },
    },
    {
        "id": "mayor-open",
        "title": "열린구청장실",
        "url": "https://bukgu.gwangju.kr/mayor/open",
        "canonical_url": "https://bukgu.gwangju.kr/mayor/open",
        "category": "menu",
        "content_type": "page",
        "score": 0.0,
        "text": "열린구청장실 구청장 인사말 구청장 프로필 북구청장 소개",
        "summary": "북구청장 인사말 및 프로필 페이지",
        "metadata": {
            "link_texts": ["열린구청장실", "구청장 인사말", "구청장 프로필"],
            "fetch_status": "fetched",
        },
    },
]


# ------------------------------------------------------------------
# Helper: build an in-memory KeywordSearcher from JSONL file
# ------------------------------------------------------------------


def _build_searcher(tmp_path: Path, docs: list[dict] = DOCS) -> KeywordSearcher:
    index_path = tmp_path / "stage368-bukgu-synonym-index.jsonl"
    with open(index_path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    return KeywordSearcher(index_path=str(index_path))


def _top_hits_for(
    searcher: KeywordSearcher,
    question: str,
    *,
    site_id: str | None,
    top_k: int = 3,
) -> list[str]:
    """Return ordered list of doc ids hit by site_id-aware rewrite.

    Mirrors ``PipelineRunner._search_for_candidates`` semantics:
    runs the searcher for each candidate query and deduplicates by
    canonical_url while preserving first-hit order. We sort the
    final list by descending score for determinism in the assertions.
    """
    rewrite = rewrite_query_candidates(
        question, site_id=site_id, max_queries=20,
    )
    seen_urls: set[str] = set()
    merged: list[dict] = []
    for q in rewrite.queries:
        for result in searcher.search(q, top_k=top_k):
            canon = result.get("canonical_url") or result.get("url", "")
            if canon and canon not in seen_urls:
                seen_urls.add(canon)
                merged.append(result)

    merged.sort(key=lambda r: (-r.get("score", 0), r.get("canonical_url", "")))
    return [r.get("id") for r in merged]


# ------------------------------------------------------------------
# Test classes
# ------------------------------------------------------------------


class TestBukguSynonymOfflineRetrieval:
    """site_id-aware offline retrieval evidence for the first slice."""

    def test_minwon_question_retrieves_minwon_doc(self, tmp_path):
        """\"민원 어디서 해?\" on real bukgu site_id should retrieve a
        minwon doc (종합민원 or 민원서식)."""
        searcher = _build_searcher(tmp_path)
        hits = _top_hits_for(
            searcher, "민원 어디서 해?", site_id="bukgu_gwangju",
        )
        assert hits, "Expected at least one retrieval hit"
        assert hits[0] in {"minwon-jonghap", "minwon-seosik"}, (
            f"Expected first hit to be a minwon doc, got {hits}"
        )

    def test_gonggo_question_retrieves_gonggo_doc(self, tmp_path):
        """\"공고 어디서 봐?\" on real bukgu site_id should retrieve
        the 고시공고 board doc."""
        searcher = _build_searcher(tmp_path)
        hits = _top_hits_for(
            searcher, "공고 어디서 봐?", site_id="bukgu_gwangju",
        )
        assert hits, "Expected at least one retrieval hit"
        assert hits[0] == "gosi-gonggo", (
            f"Expected gosi-gonggo as first hit, got {hits}"
        )

    def test_education_question_retrieves_education_doc(self, tmp_path):
        """\"교육 신청 어디서 해?\" on real bukgu site_id should
        surface the 교육접수 doc within the top hits.

        Note: the global rewriter's ``신청`` token also fires the
        민원 pattern, so the minwon docs may score higher. The
        end-to-end evidence we want is that the bukgu slice's
        ``교육접수`` synonym is enough to retrieve the education
        doc — it does not have to be the single first hit.
        """
        searcher = _build_searcher(tmp_path)
        hits = _top_hits_for(
            searcher, "교육 신청 어디서 해?", site_id="bukgu_gwangju",
        )
        assert hits, "Expected at least one retrieval hit"
        assert "education-jeopsu" in hits, (
            f"Expected education-jeopsu in top hits, got {hits}"
        )

    def test_mayor_question_does_not_retrieve_minwon_or_education(
        self, tmp_path
    ):
        """\"구청장이 누구야?\" must not surface 민원/교육 docs as the
        first hit. Mayor-only path may surface 열린구청장실 or return
        the mayor doc; the guard is the negative assertion below."""
        searcher = _build_searcher(tmp_path)
        hits = _top_hits_for(
            searcher, "구청장이 누구야?", site_id="bukgu_gwangju",
        )
        # First hit (if any) must NOT be a minwon or education doc.
        if hits:
            assert hits[0] != "minwon-jonghap"
            assert hits[0] != "minwon-seosik"
            assert hits[0] != "education-jeopsu"

    def test_no_site_id_minwon_question_falls_back_globally(self, tmp_path):
        """site_id 없이도 글로벌 deterministic rewriter가 동작해야 함.
        None이거나 minwon-*로 시작하면 OK."""
        searcher = _build_searcher(tmp_path)
        hits = _top_hits_for(
            searcher, "민원 어디서 해?", site_id=None,
        )
        assert hits == [] or hits[0].startswith("minwon-"), (
            f"Expected None or minwon-* first hit, got {hits}"
        )

    def test_offline_retrieval_uses_no_network_or_provider(
        self, tmp_path, monkeypatch,
    ):
        """검색 path는 network/provider를 호출하지 않아야 함.

        rewrite + search 호출이 정상 동작하는지, 그리고 import 단계에서
        network-style 모듈이 fetch 되지 않았는지 확인한다.
        """
        searcher = _build_searcher(tmp_path)

        # Run a search end-to-end with site_id. Must not raise.
        rewrite = rewrite_query_candidates(
            "교육 신청 어디서 해?", site_id="bukgu_gwangju",
        )
        results = searcher.search(rewrite.queries[0], top_k=3)
        assert isinstance(results, list)
        assert isinstance(rewrite.queries, tuple)

        # Verify KeywordSearcher source does not import network modules.
        import ast

        ks_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "search", "keyword_searcher.py",
        )
        with open(os.path.abspath(ks_path), "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)

        banned = (
            "requests", "httpx", "urllib3", "urllib.request",
            "firecrawl", "src.llm", "src.fetch",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for b in banned:
                        if alias.name == b or alias.name.startswith(b + "."):
                            pytest.fail(
                                f"keyword_searcher should not import: {alias.name}"
                            )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for b in banned:
                        if node.module == b or node.module.startswith(b + "."):
                            pytest.fail(
                                f"keyword_searcher should not import from: {node.module}"
                            )


class TestBukguSynonymPipelineIntegrationGap:
    """Document the integration gap revealed by Stage 368.

    ``PipelineRunner._step_search`` currently calls
    ``rewrite_query_candidates(query, max_queries=self.top_k)``
    *without* forwarding ``site_id``. As a result, even when a caller
    provides a site_id to the pipeline, the in-pipeline query rewrite
    does not benefit from the bukgu synonym slice.

    This is not a regression: it is the pre-existing plumbing gap
    that the contract in Stage 363 left open. Stage 368 records it
    explicitly so a follow-up stage can wire it through.
    """

    def test_pipeline_runner_search_step_does_not_forward_site_id(
        self,
    ):
        """Confirm that ``_step_search`` does not pass site_id to
        ``rewrite_query_candidates``.

        This is the documented gap. If a future stage wires site_id
        through, this test should be updated to assert the new
        behavior and add a positive retrieval test.
        """
        import ast

        runner_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "pipeline", "pipeline_runner.py",
        )
        with open(os.path.abspath(runner_path), "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)

        # Find the call site of rewrite_query_candidates inside _step_search
        found_in_step_search = False
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "rewrite_query_candidates"
            ):
                # Check if it has a site_id keyword
                has_site_id = any(
                    kw.arg == "site_id" for kw in node.keywords
                )
                if not has_site_id:
                    found_in_step_search = True
                    break
                # If site_id is present, that's the future-state pass
                # we want; this test would then need to be updated.
                pytest.fail(
                    "PipelineRunner now forwards site_id; update this "
                    "test to assert positive behavior."
                )

        assert found_in_step_search, (
            "Expected at least one rewrite_query_candidates() call "
            "in pipeline_runner that does NOT pass site_id (the gap). "
            "If this fails, site_id is already wired through."
        )
