import os
import re
import json
from urllib.parse import urlparse

def normalize_text(text):
    if not text:
        return ""
    text_lower = text.lower()
    cleaned = re.sub(r'[:\s,\.\(\)\[\]/\\\-_?&=~;!@#$^*+`·<>"\']+', ' ', text_lower)
    return cleaned

# Korean particles/suffixes to strip from query tokens (Stage 36)
_KOREAN_PARTICLES = (
    "은", "는", "이", "가", "을", "를", "에", "의", "로", "으로",
    "과", "와", "도", "만", "에서", "까지", "부터", "이라", "라고",
    "며", "면", "지만", "거나", "든지", "요", "죠", "까요",
)


def _strip_particles(token: str) -> str:
    """Strip common Korean particles/suffixes from a token."""
    for p in _KOREAN_PARTICLES:
        if token.endswith(p) and len(token) > len(p) + 1:
            return token[: -len(p)]
    return token


def tokenize(text):
    cleaned = normalize_text(text)
    raw_tokens = cleaned.split()

    seen = set()
    tokens = []
    for token in raw_tokens:
        if len(token) > 1:
            if token not in seen:
                seen.add(token)
                tokens.append(token)
            # Stage 36: add particle-stripped form as extra token
            stripped = _strip_particles(token)
            if stripped != token and stripped not in seen and len(stripped) > 1:
                seen.add(stripped)
                tokens.append(stripped)
    return tokens

def make_snippet(doc, query_tokens, max_length=160):
    text_sources = [
        doc.get("text", ""),
        doc.get("summary", ""),
        doc.get("metadata", {}).get("description", "")
    ]
    
    selected_text = ""
    found_pos = -1
    
    for src in text_sources:
        if not src:
            continue
        src_lower = src.lower()
        first_pos = -1
        for token in query_tokens:
            pos = src_lower.find(token.lower())
            if pos != -1:
                if first_pos == -1 or pos < first_pos:
                    first_pos = pos
        if first_pos != -1:
            selected_text = src
            found_pos = first_pos
            break
            
    if not selected_text:
        title = doc.get("title", "")
        return re.sub(r'\s+', ' ', title).strip()
        
    start = max(0, found_pos - max_length // 2)
    end = start + max_length
    if end > len(selected_text):
        end = len(selected_text)
        start = max(0, end - max_length)
        
    snippet_text = selected_text[start:end]
    if start > 0:
        snippet_text = "…" + snippet_text
    if end < len(selected_text):
        snippet_text = snippet_text + "…"
        
    return re.sub(r'\s+', ' ', snippet_text).strip()

class KeywordSearcher:
    def __init__(self, index_path=None):
        self.docs = []
        self.errors = []
        if index_path:
            self.load_index(index_path)

    def load_index(self, index_path):
        self.docs = []
        self.errors = []
        with open(index_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    self.docs.append(json.loads(line))
                except Exception as e:
                    self.errors.append(f"Line {line_no} JSON parse error: {str(e)}")

    def search(self, query, top_k=5, category=None, content_type=None):
        if not query:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        query_phrase = query.lower().strip()
        
        weights = {
            "title": 8.0,
            "metadata.link_texts": 7.0,
            "category": 5.0,
            "summary": 4.0,
            "text": 2.0,
            "metadata.description": 2.0,
            "url": 1.0,
            "canonical_url": 1.0
        }

        results = []

        for doc in self.docs:
            if category and doc.get("category", "").lower() != category.lower():
                continue
            if content_type and doc.get("content_type", "").lower() != content_type.lower():
                continue

            score = 0.0
            matched_terms = []
            matched_fields = set()

            fields_text = {
                "title": normalize_text(doc.get("title", "")),
                "metadata.link_texts": normalize_text(" ".join(doc.get("metadata", {}).get("link_texts", []))),
                "category": doc.get("category", "").lower(),
                "summary": normalize_text(doc.get("summary", "")),
                "text": normalize_text(doc.get("text", "")),
                "metadata.description": normalize_text(doc.get("metadata", {}).get("description", "")),
                "url": doc.get("url", "").lower(),
                "canonical_url": doc.get("canonical_url", "").lower()
            }

            for token in query_tokens:
                token_matched = False
                for field, f_text in fields_text.items():
                    if token in f_text:
                        score += weights[field]
                        matched_fields.add(field)
                        token_matched = True
                # Stage 36: N-gram fallback for compound tokens
                # e.g. "고시공고" in "고시 공고 입법예고" via bigram match
                if not token_matched and len(token) >= 4:
                    for n in (3, 2):
                        grams = [token[i : i + n] for i in range(0, len(token) - n + 1, n)]
                        for field_name, field_text in fields_text.items():
                            if field_name in ("title", "metadata.link_texts"):
                                if all(g in field_text for g in grams):
                                    score += weights[field_name] * 0.8
                                    matched_fields.add(field_name)
                                    token_matched = True
                        if token_matched:
                            break
                if token_matched:
                    matched_terms.append(token)

            # Phrase Bonus
            if query_phrase:
                if query_phrase in fields_text["title"] or query_phrase in fields_text["metadata.link_texts"]:
                    score += 5.0
                    if query_phrase in fields_text["title"]:
                        matched_fields.add("title")
                    if query_phrase in fields_text["metadata.link_texts"]:
                        matched_fields.add("metadata.link_texts")
                        
                if query_phrase in fields_text["text"] or query_phrase in fields_text["summary"]:
                    score += 2.0
                    if query_phrase in fields_text["text"]:
                        matched_fields.add("text")
                    if query_phrase in fields_text["summary"]:
                        matched_fields.add("summary")

            # Fetch Status Bonus
            if doc.get("metadata", {}).get("fetch_status") == "fetched":
                score += 1.0

            # Attachment Penalty
            if doc.get("content_type") == "attachment":
                has_doc_token = False
                doc_tokens = {"신청서", "양식", "첨부", "파일", "pdf", "hwp", "docx", "xlsx"}
                for t in query_tokens:
                    if t.lower() in doc_tokens:
                        has_doc_token = True
                        break
                
                if doc.get("category") == "document" and has_doc_token:
                    pass
                else:
                    score -= 1.0

            if not matched_fields or score <= 0:
                continue

            snippet = make_snippet(doc, query_tokens)

            results.append({
                "id": doc.get("id"),
                "title": doc.get("title", ""),
                "url": doc.get("url", ""),
                "canonical_url": doc.get("canonical_url", ""),
                "category": doc.get("category", "unknown"),
                "content_type": doc.get("content_type", "page"),
                "score": score,
                "matched_terms": sorted(list(set(matched_terms))),
                "matched_fields": sorted(list(matched_fields)),
                "snippet": snippet,
                "metadata": {
                    "source_types": doc.get("source_types", []),
                    "fetch_status": doc.get("metadata", {}).get("fetch_status", ""),
                    "description": doc.get("metadata", {}).get("description", "")
                }
            })

        # Sort by -score, then canonical_url
        sorted_results = sorted(results, key=lambda x: (-x["score"], x["canonical_url"]))

        final_results = []
        for rank, res in enumerate(sorted_results[:top_k], start=1):
            res["rank"] = rank
            final_results.append(res)

        return final_results
