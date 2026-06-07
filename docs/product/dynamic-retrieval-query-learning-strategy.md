# Dynamic Retrieval and Query Learning Strategy

## 1. Purpose

400-ai-finder should not become a static scenario-answer system. The product goal is to let users ask natural questions about a target official site.

* **New or long-tail questions** should use live retrieval + LLM.
* **Repeated, high-confidence, stable questions** may be promoted into scenarios/snapshots/cache for speed and reliability.

> **Principle**:  
> LLM/live retrieval is the default path.  
> Scenario/snapshot/cache is the acceleration path.

---

## 2. Problem Discovered in Stage 340

> Stage 340 found that a scenario-outside question such as "구청장이 누구야?" could be incorrectly routed to unrelated snapshot sources.
> The immediate stale-source bug was fixed in Stage 341.
> However, the broader product issue remains: the system lacks dynamic query rewriting, query learning, and scenario promotion.

* Stage 341 fixed stale source reuse.
* But fixing stale sources only prevents bad grounding.
* It does not make the system good at finding new answers.

---

## 3. Current Architecture Limits

```txt
- KeywordSearcher uses raw query tokenization.
- Korean particle stripping and n-gram fallback exist, but semantic query expansion does not.
- No LLM query rewriter exists.
- No synonym or menu-term expansion exists.
- No question logging exists.
- No repeated-question analytics exists.
- No dynamic scenario/cache promotion exists.
- Snapshot/scenario data is useful for demos and regression tests, but cannot cover all user questions.
```

---

## 4. Target Product Architecture

```
User question
  ↓
Question normalization
  ↓
Fast-path lookup:
  - exact scenario/cache hit
  - high-confidence repeated question hit
  ↓
If no high-confidence hit:
  dynamic query rewrite / expansion
  ↓
live retrieval from target site
  ↓
source ranking and domain grounding
  ↓
LLM grounded answer composition
  ↓
answer + source URLs
  ↓
question/result logging
  ↓
analytics and scenario/cache promotion candidate generation
```

### Fast Path vs Default Path

| Path | Use Case | Data Source |
|------|----------|-------------|
| **Fast path** | Stable, repeated, already-validated questions | scenario/snapshot/cache |
| **Default path** | New, changing, long-tail, time-sensitive questions | live retrieval + LLM |

---

## 5. Scenario/Snapshot Role

### Scenarios/snapshots ARE for:

```txt
- demo stability
- smoke tests
- regression tests
- repeated FAQ acceleration
- offline mode
- known stable pages
```

### Scenarios/snapshots are NOT for:

```txt
- covering every possible user question
- replacing live retrieval
- answering changing information without source refresh
- hardcoding one-off answers
```

> Adding a "구청장" scenario is not the product-level solution.  
> The product-level solution is better retrieval and question learning.

---

## 6. Dynamic Query Rewrite Strategy

### First-Stage Query Rewriting

| User Question | Candidate Retrieval Queries |
|--------------|----------------------------|
| 구청장이 누구야? | 북구청장, 구청장 인사말, 구청장 프로필, 열린구청장, 북구청장 소개 |
| 청년 일자리 어디서 봐? | 청년, 일자리, 채용, 고용, 경제, 비즈광주북구 |

### Design Requirements

```txt
- Query rewrite should be provider-optional at first.
- It should support mock/stub tests.
- It must never fabricate answers.
- It should output search terms, not final answers.
- It should be auditable in logs.
- It should preserve the original user question.
```

---

## 7. No-Results and Source Mismatch Guard

### If retrieval returns no relevant sources:

```txt
- answer should say relevant official source was not found
- do not answer using stale or unrelated sources
- suggest alternative keywords or official menu terms
```

### If sources are weak:

```txt
- return WARN-style answer
- show sources
- say that the result may require official-site confirmation
```

### If source topic and question topic mismatch:

```txt
- do not compose a confident answer
- prefer no-results or low-confidence response
```

> Stage 341 implemented the first guard by clearing stale snapshot sources when fallback matching returns empty.

---

## 8. Question Logging and Analytics

### Log Fields (conceptual design only — not implemented)

```txt
- timestamp
- site_id
- normalized question
- raw question
- provider mode
- retrieval mode
- search terms used
- result count
- source domains
- answer status: PASS / WARN / NO_RESULTS / ERROR
- fallback_used
- user feedback if available
```

### Privacy/Security Rules

```txt
- do not log API keys
- do not log secrets
- avoid storing personally sensitive information unless necessary
- consider hashing user/session identifiers if added later
```

---

## 9. Query Learning and Scenario Promotion

### Promotion Flow

```
Question logs
  ↓
Cluster similar questions
  ↓
Detect repeated questions
  ↓
Check retrieval quality and answer success
  ↓
Generate scenario/cache candidate
  ↓
Human review
  ↓
Promote to validated scenario/snapshot/cache
```

### Candidate Promotion Criteria

```txt
- repeated more than a threshold, e.g. 3+ times per week
- stable answer source
- official-domain grounded
- low failure rate
- no sensitive or personal query content
- reviewer approval
```

> Do not auto-promote directly to committed fixtures without review.

---

## 10. Metrics

```txt
- no-results rate
- fallback rate
- source mismatch rate
- official-domain grounding rate
- repeated-question rate
- scenario/cache hit rate
- user re-question rate
- low-confidence answer rate
- query rewrite success rate
```

### Why These Matter

* They show where retrieval is failing.
* They show which questions should become scenario/cache candidates.
* They help distinguish product gaps from site-structure gaps.

---

## 11. Implementation Roadmap

### P0 — Already Completed
- Clear stale snapshot sources when fallback matching returns empty (Stage 341)

### P1 — Next
- Add query rewriter design and test boundary
- Add source mismatch / no-results guard hardening
- Add query rewrite logging in dry-run/mock mode

### P2
- Add question logging
- Add analytics report for repeated questions
- Add scenario/cache promotion candidate generator

### P3
- Add hybrid keyword + vector search
- Add semantic menu matching
- Add site-specific synonym dictionaries

---

## 12. Non-Goals

```txt
- Do not create scenarios for every possible question.
- Do not hardcode "구청장" or other one-off answers.
- Do not make LLM answer without grounded sources.
- Do not require live provider for offline tests.
- Do not break existing snapshot/demo behavior.
```

---

## Implementation Status

### Stage 341 — P0 Bug Fix (Completed)
- Clear stale snapshot sources when fallback matching returns empty.

### Stage 343 — Query Rewriter Contract (Completed)
- Added `src/search/query_rewriter.py` with offline-safe deterministic query rewriter.
- Produces retrieval query candidates only — does not generate answers.
- Supports mayor, youth/jobs, civil service, notice, welfare, and education query patterns.
- Preserves original question exactly, deduplicates candidates, limits to `max_queries`.
- No live LLM/API/network calls.
- 18 contract tests added in `tests/test_query_rewriter.py`.

### Stage 344a — Query Rewriter Pipeline Integration (Completed)
- Integrates deterministic query rewrite candidates into the offline-testable pipeline search path.
- Original question preserved for answer composition in `query_rewrite` metadata.
- Results across rewritten queries are deduplicated by canonical URL.
- Existing keyword search behavior preserved for ordinary questions.
- 8 integration tests added in `tests/test_query_rewriter_pipeline_integration.py`.

### Stage 344b — Source Mismatch Guard Hardening (Completed)
- Stage 344b adds source mismatch guard hardening for weak retrieval results. The guard prevents confident answers from being composed when retrieved sources do not sufficiently align with the original user question.

### Stage 351 — Question Logging Boundary (Completed)
- Stage 351 adds an offline-safe question logging boundary. The initial boundary supports sanitized structured question events and optional local JSONL logging, without analytics, clustering, scenario promotion, external storage, or live provider calls.

### Stage 352 — Repeated-Question Analytics and Promotion Planning (Completed)
- Stage 352 adds repeated-question analytics and scenario/cache promotion planning. The boundary treats repeated questions as human-review candidates only and does not automatically create scenarios, snapshots, caches, or pull requests.

### Stage 353 — Repeated-Question Analytics Dry-Run Report (Completed)
- Stage 353 adds a local dry-run repeated-question analytics report for human review. It keeps promotion manual and does not write scenario/snapshot/cache files.
- The CLI reads sanitized JSONL question logs and produces a Markdown report separating promotion candidates from retrieval gaps.
- No live network, LLM, fetch, or external storage calls are used.

### Stage 354 — Operator Question Log Guide (Completed)
- Stage 354 adds an operator guide for collecting sanitized question logs and running local dry-run analytics reports. It keeps logging local/offline and requires human review before any scenario/cache promotion.
- The guide documents safe JSONL format, what must never be logged, the dry-run report command, and the human review workflow.
- No code or test changes. Docs-only.

### Stage 355 — Scenario/Cache Promotion Review Workflow (Completed)
- Stage 355 adds the human review workflow for scenario/cache promotion candidates. It defines how dry-run report candidates should be classified as cache review, scenario review, retrieval gaps, or monitor-only items, without automatic promotion.
- Adds review checklists, a decision matrix, and follow-up issue templates for cache, scenario, and retrieval-gap candidates.
- Cross-linked from the repeated-question analytics promotion plan and the operator quickstart.
- No code or test changes. Docs-only.

### Stage 356 — Promotion Candidate Review Template (Completed)
- Stage 356 adds a copy-pasteable promotion candidate review template for human reviewers. It supports cache, scenario, retrieval gap, monitor-only, and reject decisions without automatic promotion.
- Includes a decision guide table, per-category checklists, and a synthetic completed review example.
- Cross-linked from the scenario/cache promotion review workflow, the repeated-question analytics promotion plan, and the operator quickstart.
- No code or test changes. Docs-only.

### Stage 357 — Synthetic Promotion Dry-Run Operator Guide (Completed)
- Stage 357 adds a synthetic-only operator dry-run guide showing how to run repeated-question analytics with local JSONL examples and copy findings into the promotion candidate review template.
- The guide demonstrates cache candidate, scenario candidate, retrieval gap, and monitor-only review outcomes.
- No code or test changes. Docs-only.
- No live network, LLM, fetch, Firecrawl, scenario, snapshot, cache, PR, or automatic promotion behavior is added.

---

## 13. Example: "구청장이 누구야?"

### Correct Behavior After Stage 341

```txt
Snapshot mode:
- no relevant fallback source
- no stale source reuse
- no-results response
```

### Target Future Behavior

```txt
Live retrieval mode:
- rewrite query to "북구청장", "구청장 프로필", "열린구청장"
- retrieve official source
- compose grounded answer with source URL
```

### Scenario Role

```txt
If many users repeatedly ask this and the source is stable, promote a validated mayor_identity scenario/cache entry after human review.
```

---

## 14. Open Follow-Up Candidates

> List issue candidates but do not create all unless instructed.

Recommended follow-ups:

```txt
[TECH] Add query rewriter contract for live retrieval
[TECH] Add source mismatch guard for weak retrieval results
[TECH] Add question logging boundary
[PRODUCT] Define scenario/cache promotion review workflow
[TECH] Add repeated-question analytics report
```