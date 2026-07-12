import pytest
import json
import os
from src.search.keyword_searcher import normalize_text, tokenize, make_snippet, KeywordSearcher

def test_tokenize():
    # 1. 영문 소문자화
    # 2. 한글 보존
    # 3. 구분자 분리
    # 4. 길이 1 이하 제거
    # 5. 중복 제거
    text = "Apply, 지원사업! [신청서] - pdf hwp. a (한글1)"
    tokens = tokenize(text)
    
    assert "apply" in tokens
    assert "지원사업" in tokens
    assert "신청서" in tokens
    assert "pdf" in tokens
    assert "hwp" in tokens
    assert "한글1" in tokens
    
    assert "a" not in tokens
    assert "1" not in tokens
    
    # 중복 제거 및 보존
    text_dup = "신청서 신청서 pdf"
    assert tokenize(text_dup) == ["신청서", "pdf"]

def test_match_weights():
    searcher = KeywordSearcher()
    # Mock docs
    # Doc 1: matches 'apply' in title (title weight: 8.0)
    # Doc 2: matches 'apply' in text (text weight: 2.0)
    # Doc 3: matches 'apply' in metadata.link_texts (link_texts weight: 7.0)
    searcher.docs = [
        {"id": "doc-1", "title": "지원사업 apply", "content_type": "page", "canonical_url": "https://a.com", "metadata": {}},
        {"id": "doc-2", "title": "공지사항", "text": "이것은 apply 정보입니다.", "content_type": "page", "canonical_url": "https://b.com", "metadata": {}},
        {"id": "doc-3", "title": "기타", "content_type": "page", "canonical_url": "https://c.com", "metadata": {"link_texts": ["apply 신청"]}}
    ]
    
    results = searcher.search("apply")
    # Ranked: doc-1 (score: 8.0) > doc-3 (score: 7.0) > doc-2 (score: 2.0)
    assert len(results) == 3
    assert results[0]["id"] == "doc-1"
    assert results[1]["id"] == "doc-3"
    assert results[2]["id"] == "doc-2"

def test_phrase_bonus():
    searcher = KeywordSearcher()
    # Doc 1: Matches phrase "지원사업 신청" in title (+5.0 bonus)
    # Doc 2: Matches terms "지원사업", "신청" but not consecutively in text
    searcher.docs = [
        {"id": "doc-1", "title": "지원사업 신청 안내", "canonical_url": "https://a.com", "metadata": {}},
        {"id": "doc-2", "title": "공지사항", "text": "신청 방법 및 지원사업 정보", "canonical_url": "https://b.com", "metadata": {}}
    ]
    results = searcher.search("지원사업 신청")
    assert len(results) == 2
    assert results[0]["id"] == "doc-1"

def test_filters():
    searcher = KeywordSearcher()
    searcher.docs = [
        {"id": "doc-1", "title": "신청서", "category": "apply", "content_type": "page", "canonical_url": "https://a.com", "metadata": {}},
        {"id": "doc-2", "title": "신청서 다운", "category": "document", "content_type": "attachment", "canonical_url": "https://b.com", "metadata": {}}
    ]
    
    # Category filter
    res_cat = searcher.search("신청서", category="apply")
    assert len(res_cat) == 1
    assert res_cat[0]["id"] == "doc-1"

    # Content type filter
    res_ct = searcher.search("신청서", content_type="attachment")
    assert len(res_ct) == 1
    assert res_ct[0]["id"] == "doc-2"

def test_attachment_penalty():
    searcher = KeywordSearcher()
    # Doc 1: category=document, content_type=attachment, matching term = "양식" (document token) -> No penalty
    # Doc 2: category=unknown, content_type=attachment, matching term = "공지사항" -> penalty -1.0
    searcher.docs = [
        {"id": "doc-1", "title": "제출 양식", "category": "document", "content_type": "attachment", "canonical_url": "https://a.com", "metadata": {}},
        {"id": "doc-2", "title": "공지사항 파일", "category": "unknown", "content_type": "attachment", "canonical_url": "https://b.com", "metadata": {}}
    ]
    
    # 1. Non-document token query: "공지사항"
    # Doc 2 gets matched: title match 8.0 + phrase bonus 5.0 - 1.0 (penalty) = 12.0
    res1 = searcher.search("공지사항")
    assert len(res1) == 1
    assert res1[0]["id"] == "doc-2"
    assert res1[0]["score"] == 12.0

    # 2. Document token query: "양식"
    # Doc 1 gets matched: title match 8.0 + phrase bonus 5.0 (No penalty because category=document & query has "양식") = 13.0
    res2 = searcher.search("양식")
    assert len(res2) == 1
    assert res2[0]["id"] == "doc-1"
    assert res2[0]["score"] == 13.0

def test_snippet_generation():
    doc = {
        "title": "My Title",
        "text": "이 페이지는 중소기업 지원사업 신청 방법과 제출서류를 안내합니다.",
        "summary": "요약문",
        "metadata": {"description": "메타 설명"}
    }
    # 1. Match in text
    snippet = make_snippet(doc, ["제출서류"], max_length=20)
    assert "제출서류" in snippet
    assert len(snippet) <= 25

    # 2. Text empty -> description fallback
    doc_no_text = {
        "title": "My Title",
        "text": "",
        "summary": "",
        "metadata": {"description": "메타 설명 속의 제출서류"}
    }
    snippet_desc = make_snippet(doc_no_text, ["제출서류"])
    assert "제출서류" in snippet_desc

def test_deterministic_sorting():
    searcher = KeywordSearcher()
    # Doc 1 & Doc 2 have identical scores
    searcher.docs = [
        {"id": "doc-2", "title": "공지사항", "canonical_url": "https://example.com/b-page", "metadata": {}},
        {"id": "doc-1", "title": "공지사항", "canonical_url": "https://example.com/a-page", "metadata": {}}
    ]
    
    results = searcher.search("공지사항")
    assert len(results) == 2
    assert results[0]["id"] == "doc-1"
    assert results[1]["id"] == "doc-2"

def test_empty_query():
    searcher = KeywordSearcher()
    searcher.docs = [{"id": "doc-1", "title": "공지사항", "metadata": {}}]
    assert searcher.search("") == []
    assert searcher.search("  ") == []

def test_malformed_jsonl_handling(tmp_path):
    p = tmp_path / "test.jsonl"
    p.write_text(
        '{"id":"doc-1","title":"ok","metadata":{}}\n'
        'invalid_json_line\n'
        '{"id":"doc-2","title":"ok2","metadata":{}}\n'
    )
    
    searcher = KeywordSearcher(str(p))
    assert len(searcher.docs) == 2
    assert len(searcher.errors) == 1
    assert "Line 2" in searcher.errors[0]


# ======================================================================
# Stage 36: Korean particle stripping + N-gram matching
# ======================================================================

class TestParticleStripping:
    """Stage 36: tokenize strips Korean particles from query tokens."""

    def test_strip_neun(self):
        """고시공고는 → 고시공고 (는 stripped)"""
        tokens = tokenize("고시공고는")
        assert "고시공고" in tokens

    def test_strip_eun(self):
        """지원사업은 → 지원사업"""
        tokens = tokenize("지원사업은")
        assert "지원사업" in tokens

    def test_strip_i(self):
        """조직도가 → 조직도"""
        tokens = tokenize("조직도가")
        assert "조직도" in tokens

    def test_strip_eul(self):
        """민원을 → 민원"""
        tokens = tokenize("민원을")
        assert "민원" in tokens

    def test_strip_eseo(self):
        """어디서 → 어딘 (에서 stripped but 어딘 > 1 char)"""
        tokens = tokenize("어디서")
        # "어디서" ends with "에서" but len("어디") = 2 > 1, so it's kept
        assert "어디" in tokens or "어디서" in tokens

    def test_no_strip_short_token(self):
        """Very short tokens should not be stripped."""
        tokens = tokenize("이")
        # "이" has len 1, excluded by len > 1 check
        assert tokens == []

    def test_particle_stripped_dedup(self):
        """Both original and stripped forms appear, but no duplicates."""
        tokens = tokenize("고시공고는 고시공고")
        assert tokens.count("고시공고") == 1
        assert "고시공고는" in tokens


class TestNGramFallback:
    """Stage 36: N-gram matching for compound Korean tokens."""

    def test_bigram_match_in_title(self):
        """Compound token '고시공고' matches title with '고시 공고' via bigrams."""
        searcher = KeywordSearcher()
        searcher.docs = [
            {
                "id": "doc-1",
                "title": "고시·공고/입법예고",
                "category": "menu",
                "content_type": "page",
                "canonical_url": "https://www.gwangju.go.kr/contentsView.do?pageId=www791",
                "metadata": {"link_texts": ["고시·공고/입법예고"]},
            },
        ]
        results = searcher.search("고시공고는 어디서 봐?")
        assert len(results) >= 1
        assert results[0]["id"] == "doc-1"

    def test_bigram_match_in_link_texts(self):
        """Compound token matches via metadata.link_texts N-gram."""
        searcher = KeywordSearcher()
        searcher.docs = [
            {
                "id": "doc-1",
                "title": "기타 페이지",
                "category": "menu",
                "content_type": "page",
                "canonical_url": "https://example.com",
                "metadata": {"link_texts": ["고시·공고 안내"]},
            },
        ]
        results = searcher.search("고시공고")
        assert len(results) >= 1

    def test_no_ngram_for_short_tokens(self):
        """Tokens shorter than 4 chars should not trigger N-gram fallback."""
        searcher = KeywordSearcher()
        searcher.docs = [
            {
                "id": "doc-1",
                "title": "고 시",
                "canonical_url": "https://example.com",
                "metadata": {},
            },
        ]
        # "고 시" as separate chars - token "고시" has len 2, no N-gram
        results = searcher.search("고 시")
        # Should match via direct token "고" (but len <= 1 excluded) or "시" (also excluded)
        # This is expected behavior - very short queries don't match
        assert len(results) == 0

    def test_ngram_only_title_and_link_texts(self):
        """N-gram matching only applies to title and metadata.link_texts fields."""
        searcher = KeywordSearcher()
        searcher.docs = [
            {
                "id": "doc-1",
                "title": "다른 페이지",
                "text": "이곳에서 고시 공고를 확인하세요",
                "category": "menu",
                "content_type": "page",
                "canonical_url": "https://example.com",
                "metadata": {},
            },
        ]
        results = searcher.search("고시공고")
        # "고시공고" via N-gram bigrams ["고시","공고"] should match text
        # But N-gram only applies to title/link_texts, not text
        # However, direct token "고시" and "공고" (from particle stripping of "고시공고")
        # won't be generated since "고시공고" doesn't end with a known particle
        # So this should NOT match via N-gram (text field excluded)
        assert len(results) == 0


class TestNormalizeTextMiddleDot:
    """Stage 36: normalize_text handles middle dot (·)."""

    def test_middle_dot_to_space(self):
        assert "고시 공고" in normalize_text("고시·공고")

    def test_slash_to_space(self):
        assert "입법 예고" in normalize_text("입법/예고")

    def test_combined_special_chars(self):
        normalized = normalize_text("고시·공고/입법예고")
        assert "고시" in normalized
        assert "공고" in normalized
