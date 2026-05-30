"""SiteDemoRunner — grounded answer demo for a site profile.

Loads a site profile by site_id, runs the full pipeline
(→ homepage_map → document_index → enrich → search → answer),
and returns a structured result with sources.

Usage::

    runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
    result = runner.answer("민원서식 어디서 받아?")
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any

from ..pipeline.pipeline_runner import PipelineRunner
from ..site_profiles import load_profile


def _tokenize_korean(text: str) -> list[str]:
    """Simple tokenization for Korean menu keywords."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower()).strip()
    tokens = [t for t in cleaned.split() if len(t) > 1]
    return tokens


def _match_keyword_against_links(
    keywords: list[str],
    links: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find links whose title or text matches any keyword."""
    matched = []
    seen_urls: set[str] = set()
    for link in links:
        title = (link.get("title") or link.get("text") or "").strip()
        url = link.get("url", "")
        if not title or not url:
            continue
        if url in seen_urls:
            continue
        title_lower = title.lower()
        for kw in keywords:
            if kw.lower() in title_lower:
                matched.append({"title": title, "url": url})
                seen_urls.add(url)
                break
    return matched


def _fallback_sources_from_homepage_map(
    homepage_map: dict[str, Any],
    question: str,
    important_keywords: list[str],
) -> list[dict[str, Any]]:
    """Build fallback sources from homepage_map menu/navigation links.

    Strategy:
    1. Match question tokens against navigation links
    2. Match question tokens against all category links (menu, apply, notice, board, document)
    3. Match profile important_keywords against navigation links
    """
    # Collect question tokens + relevant profile keywords
    question_tokens = _tokenize_korean(question)

    # Merge with important_keywords that appear in the question
    expanded_tokens = list(question_tokens)
    for kw in important_keywords:
        kw_lower = kw.lower()
        for token in question_tokens:
            if token in kw_lower or kw_lower in token:
                if kw not in expanded_tokens:
                    expanded_tokens.append(kw)
                break

    candidates: list[dict[str, Any]] = []

    # 1. Check navigation links
    nav_links = homepage_map.get("homepage", {}).get("navigation_links", [])
    nav_matches = _match_keyword_against_links(expanded_tokens, nav_links)
    for m in nav_matches:
        candidates.append({**m, "source_type": "navigation", "score": 10.0})

    # 2. Check category links
    categories = homepage_map.get("categories", {})
    priority_cats = ["menu", "apply", "notice", "board", "document"]
    for cat in priority_cats:
        cat_links = categories.get(cat, [])
        cat_matches = _match_keyword_against_links(expanded_tokens, cat_links)
        for m in cat_matches:
            candidates.append({**m, "source_type": cat, "score": 8.0})

    # 3. Dedup by URL
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for c in candidates:
        if c["url"] not in seen:
            seen.add(c["url"])
            deduped.append(c)

    return deduped[:5]


def _extract_topic_from_question(question: str) -> str:
    """Extract the main topic keyword from a Korean question.

    Strips common particles (는/은/을/를/에서/의/에/로) from the first token.

    Examples:
        "민원서식 어디서 받아?" → "민원서식"
        "교육접수는 어디서 해?" → "교육접수"
        "고시공고는 어디서 확인해?" → "고시공고"
    """
    q = question.strip()
    tokens = _tokenize_korean(q)
    if not tokens:
        return q
    topic = tokens[0]
    # Strip common Korean particles
    particles = ("에서는", "에서", "는", "은", "을", "를", "의", "에", "로", "이", "가")
    for p in particles:
        if topic.endswith(p) and len(topic) > len(p) + 1:
            topic = topic[: -len(p)]
            break
    return topic


def _generate_answer_from_sources(
    question: str,
    sources: list[dict[str, Any]],
    site_name: str,
) -> str:
    """Generate a user-friendly answer from question + matched sources.

    Produces an AI-guide-style answer that:
    1. Acknowledges the user's topic
    2. Points to where to find it
    3. Gives next-step guidance
    4. References the source links
    """
    topic = _extract_topic_from_question(question)

    if not sources:
        return (
            f"## 답변\n\n"
            f"'{topic}' 관련 정보를 찾지 못했습니다.\n\n"
            f"## 다음 단계\n\n"
            f"{site_name} 홈페이지에서 직접 검색해 보시거나, "
            f"다른 키워드로 다시 질문해 주세요.\n\n"
            f"## 확인 필요\n\n"
            f"정확한 최신 내용은 연결된 공식 홈페이지에서 확인해 주세요."
        )

    # Build source references
    source_names = []
    for s in sources[:3]:
        title = s.get("title", "").strip()
        if title and title not in source_names:
            source_names.append(title)

    main_source = source_names[0] if source_names else topic

    answer = (
        f"## 답변\n\n"
        f"찾으시는 내용은 '{topic}'에 해당합니다.\n\n"
        f"{site_name} 홈페이지의 {main_source} 메뉴에서 "
        f"관련 정보를 확인할 수 있습니다.\n\n"
        f"아래 관련 홈페이지 바로가기를 눌러 해당 페이지로 이동해 주세요.\n\n"
        f"## 확인 필요\n\n"
        f"정확한 최신 내용은 연결된 공식 홈페이지에서 확인해 주세요."
    )

    return answer


class SiteDemoRunner:
    """Run a pipeline demo against a site profile.

    Args:
        site_id: Site profile ID (e.g. ``bukgu_gwangju``).
        provider: LLM provider name (default: ``mock``).
        fetch_provider: Fetch provider name (default: from profile).
        output_dir: Pipeline output directory. If None, uses a temp dir.
        **pipeline_kwargs: Additional PipelineRunner args (top_k, max_sources, etc.).
    """

    def __init__(
        self,
        site_id: str,
        provider: str = "mock",
        fetch_provider: str | None = None,
        output_dir: str | None = None,
        model: str | None = None,
        **pipeline_kwargs: Any,
    ) -> None:
        self.site_id = site_id
        self.provider = provider
        self.model = model
        self._fetch_provider = fetch_provider
        self._output_dir = output_dir
        self._pipeline_kwargs = pipeline_kwargs

        # Load profile
        self.profile = load_profile(site_id)

        # Resolve fetch provider
        if self._fetch_provider is None:
            self._fetch_provider = self.profile.preferred_fetch_provider

    def answer(self, question: str, output_dir: str | None = None) -> dict[str, Any]:
        """Answer a natural-language question against the site profile.

        Args:
            question: The user's question (e.g. ``민원서식 어디서 받아?``).
            output_dir: Override output directory for this run.

        Returns:
            A dict with answer, sources, search_results, and metadata.

        Raises:
            ValueError: If question is empty.
        """
        if not question or not question.strip():
            raise ValueError("Question must not be empty")

        run_dir = output_dir or self._output_dir or tempfile.mkdtemp(prefix="demo_")

        runner = PipelineRunner(
            output_dir=run_dir,
            provider=self.provider,
            fetch_provider=self._fetch_provider,
            model=self.model,
            **self._pipeline_kwargs,
        )

        pipeline_result = runner.run(
            url=self.profile.base_url,
            query=question,
        )

        # Build the demo result
        demo_result = self._build_result(question, pipeline_result, run_dir)
        return demo_result

    # ------------------------------------------------------------------
    # Result builder
    # ------------------------------------------------------------------

    def _build_result(
        self,
        question: str,
        pipeline_result: dict[str, Any],
        run_dir: str,
    ) -> dict[str, Any]:
        """Build the final structured demo result dict."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Extract search results from pipeline output
        search_results: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        warnings: list[str] = []
        fallback_used = False

        for step in pipeline_result.get("steps", []):
            if step["name"] == "search" and step["ok"]:
                sp = step.get("output", "")
                if sp and os.path.exists(sp):
                    try:
                        with open(sp, "r", encoding="utf-8") as f:
                            search_data = json.load(f)
                        search_results = search_data.get("results", [])
                    except (json.JSONDecodeError, OSError):
                        pass
                break

        # Build sources from search results
        for r in search_results:
            source = {
                "title": r.get("title", r.get("text", "")),
                "url": r.get("url", ""),
                "source_type": r.get("category", "web"),
                "snippet": (r.get("text", "") or "")[:200],
                "score": r.get("score", 0),
            }
            sources.append(source)

        # Fallback: when search_results is empty, try homepage_map menu candidates
        if not search_results:
            homepage_map = self._load_homepage_map(run_dir)
            if homepage_map:
                fallback_candidates = _fallback_sources_from_homepage_map(
                    homepage_map,
                    question,
                    self.profile.important_keywords,
                )
                for fc in fallback_candidates:
                    fallback_result = {
                        "id": f"fb-{len(search_results):05d}",
                        "title": fc["title"],
                        "url": fc["url"],
                        "canonical_url": fc["url"],
                        "category": fc.get("source_type", "menu"),
                        "content_type": "page",
                        "score": fc.get("score", 5.0),
                        "matched_terms": [],
                        "matched_fields": ["title", "metadata.link_texts"],
                        "snippet": fc["title"],
                        "metadata": {
                            "source_types": [fc.get("source_type", "menu")],
                            "fetch_status": "fallback",
                            "description": "Menu/navigation fallback from homepage map",
                        },
                    }
                    search_results.append(fallback_result)
                    sources.append({
                        "title": fc["title"],
                        "url": fc["url"],
                        "source_type": fc.get("source_type", "menu"),
                        "snippet": fc["title"][:200],
                        "score": fc.get("score", 5.0),
                    })

                if fallback_candidates:
                    fallback_used = True
                    warnings.append(
                        f"Search returned 0 results; used {len(fallback_candidates)} "
                        f"homepage map fallback candidates"
                    )

        # Extract answer
        answer = ""
        answer_ok = False
        answer_data = None
        for step in pipeline_result.get("steps", []):
            if step["name"] == "answer":
                answer_ok = step["ok"]
                if answer_ok:
                    ap = step.get("output", "")
                    if ap and os.path.exists(ap):
                        try:
                            with open(ap, "r", encoding="utf-8") as f:
                                answer_data = json.load(f)
                            answer = answer_data.get("answer_markdown", "")
                        except (json.JSONDecodeError, OSError):
                            pass
                break

        if not answer:
            answer = pipeline_result.get("answer_markdown", "")

        if not pipeline_result.get("ok", False):
            warnings.append(f"Pipeline partially failed: {pipeline_result.get('error', 'unknown')}")

        return {
            "site_id": self.site_id,
            "site_name": self.profile.name,
            "question": question,
            "answer": answer,
            "sources": sources,
            "search_results": search_results,
            "ok": pipeline_result.get("ok", False),
            "answer_ok": answer_ok,
            "provider": self.provider,
            "model": self.model or (answer_data.get("model", "") if answer_data else ""),
            "fetch_provider": self._fetch_provider,
            "output_dir": run_dir,
            "fetched_at": now,
            "fallback_used": fallback_used,
            "warnings": warnings,
        }

    @staticmethod
    def _load_homepage_map(run_dir: str) -> dict[str, Any] | None:
        """Load homepage-map.json from the pipeline run directory."""
        path = os.path.join(run_dir, "homepage-map.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    # ------------------------------------------------------------------
    # Snapshot save / load
    # ------------------------------------------------------------------

    @staticmethod
    def save_snapshot(result: dict[str, Any], path: str) -> str:
        """Save a demo result dict as a reusable JSON snapshot.

        Args:
            result: The dict returned by ``answer()``.
            path: File path to write the snapshot JSON.

        Returns:
            The absolute path of the written file.
        """
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return os.path.abspath(path)

    @staticmethod
    def load_snapshot(path: str) -> dict[str, Any]:
        """Load a demo result from a JSON snapshot file.

        Args:
            path: File path of the snapshot JSON.

        Returns:
            The loaded demo result dict.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not valid JSON or missing required keys.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Snapshot file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"Invalid snapshot file: {e}") from e

        if not isinstance(data, dict):
            raise ValueError("Snapshot file must contain a JSON object")

        # Minimal validation
        required = {"site_id", "question"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Snapshot missing required keys: {missing}")

        return data

    def answer_from_snapshot(
        self,
        snapshot_path: str,
        question: str | None = None,
    ) -> dict[str, Any]:
        """Answer using a pre-saved snapshot instead of live pipeline.

        If ``question`` is provided and differs from the snapshot's question,
        re-runs the fallback logic on the snapshot's homepage_map and
        generates a NEW answer based on the current question + matched sources.

        Args:
            snapshot_path: Path to a JSON snapshot file.
            question: Override question (optional).

        Returns:
            A demo result dict.
        """
        snapshot = self.load_snapshot(snapshot_path)

        # If question differs, rebuild sources via fallback
        q = question or snapshot.get("question", "")
        if not q or not q.strip():
            raise ValueError("Question must not be empty")

        question_changed = question and question != snapshot.get("question")

        if question_changed:
            # Re-run fallback from the snapshot's homepage_map data
            homepage_map = snapshot.get("homepage_map")
            if homepage_map:
                fb = _fallback_sources_from_homepage_map(
                    homepage_map, q, self.profile.important_keywords,
                )
                if fb:
                    snapshot["search_results"] = [
                        {
                            "id": f"fb-{i:05d}",
                            "title": c["title"],
                            "url": c["url"],
                            "canonical_url": c["url"],
                            "category": c.get("source_type", "menu"),
                            "content_type": "page",
                            "score": c.get("score", 5.0),
                            "matched_terms": [],
                            "matched_fields": ["title"],
                            "snippet": c["title"],
                            "metadata": {"fetch_status": "snapshot-fallback"},
                        }
                        for i, c in enumerate(fb)
                    ]
                    snapshot["sources"] = [
                        {
                            "title": c["title"],
                            "url": c["url"],
                            "source_type": c.get("source_type", "menu"),
                            "snippet": c["title"][:200],
                            "score": c.get("score", 5.0),
                        }
                        for c in fb
                    ]
                    snapshot["fallback_used"] = True
                    snapshot.setdefault("warnings", []).append(
                        "홈페이지 메뉴에서 찾은 결과"
                    )

            snapshot["question"] = q

            # Generate a NEW answer based on current question + sources
            snapshot["answer"] = _generate_answer_from_sources(
                q, snapshot.get("sources", []), self.profile.name,
            )

        snapshot["snapshot_mode"] = True
        snapshot["provider"] = self.provider
        if self.model:
            snapshot["model"] = self.model
        elif self.provider == "stub":
            snapshot["model"] = "stub"
        elif self.provider == "mock":
            snapshot["model"] = ""
        snapshot.setdefault("warnings", []).append(
            "홈페이지 메뉴와 저장된 데모 자료를 기준으로 안내합니다."
        )
        return snapshot


# ------------------------------------------------------------------
# Convenience function
# ------------------------------------------------------------------


def run_demo(
    site_id: str,
    question: str,
    provider: str = "mock",
    fetch_provider: str | None = None,
    output_dir: str | None = None,
    snapshot: str | None = None,
    save_snapshot: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """One-shot convenience function around SiteDemoRunner.

    Args:
        site_id: Site profile ID.
        question: Natural-language question.
        provider: LLM provider name (default: ``mock``).
        fetch_provider: Fetch provider name (default: from profile).
        output_dir: Output directory (default: temp dir).
        snapshot: Path to a snapshot file to use instead of live fetch.
        save_snapshot: Path to save the live result as a snapshot.
        **kwargs: Additional PipelineRunner args.

    Returns:
        A dict with answer, sources, and metadata.
    """
    runner = SiteDemoRunner(
        site_id=site_id,
        provider=provider,
        fetch_provider=fetch_provider,
        output_dir=output_dir,
        **kwargs,
    )

    if snapshot:
        result = runner.answer_from_snapshot(snapshot, question=question)
    else:
        result = runner.answer(question)

    if save_snapshot:
        SiteDemoRunner.save_snapshot(result, save_snapshot)

    return result
