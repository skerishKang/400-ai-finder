# Promotion Candidate Review Template

## 1. Purpose

This template helps operators and reviewers evaluate candidates from repeated-question analytics dry-run reports.

It is for **human review only**.

Using this template does **not** automatically create scenarios, snapshots, caches, pull requests, or commits.

---

## 2. When to use this template

Use this template when:

- A dry-run report identifies a repeated successful question.
- A dry-run report identifies a repeated NO_RESULTS/WARN retrieval gap.
- A reviewer needs to decide whether the item should become:
  - cache review candidate
  - scenario review candidate
  - retrieval improvement issue
  - monitor-only item
  - reject / do not use

Do **not** use this template when:

- The report contains unsanitized personal or sensitive data.
- The candidate contains API keys, secrets, tokens, Authorization headers, or private identifiers.
- The question is a one-off event with no repeated pattern.
- The source domain cannot be verified.

If any of the "do not use" conditions apply, the report must be re-sanitized or the candidate excluded before review.

---

## 3. Copy-paste review template

Copy the block below into a new review file (e.g. `docs/reviews/promotion-candidate-<date>-<key>.md`) and fill in each field.

```md
# Promotion Candidate Review

## Candidate summary

- Review date:
- Reviewer:
- Source report:
- Site ID:
- Normalized key:
- Representative question:
- Example questions:
  - 
  - 
  - 

## Frequency and status

- Total count:
- Time window:
- Answer status distribution:
  - PASS:
  - WARN:
  - NO_RESULTS:
  - ERROR:
- fallback_used count:
- guard_status / guard_reason:
- Query rewrite terms:
  - 

## Source grounding

- Source domains:
  - 
- Official source confirmed:
  - [ ] Yes
  - [ ] No
  - [ ] Unclear
- Source stability:
  - [ ] Stable
  - [ ] Volatile / time-sensitive
  - [ ] Unknown
- Notes on source reliability:

## Safety and privacy check

- [ ] No API keys or secrets present
- [ ] No Authorization headers or Bearer tokens present
- [ ] No private user identifiers present
- [ ] Raw question content is sanitized enough for review
- [ ] Candidate does not require storing sensitive personal data

## Decision category

Select one:

- [ ] Cache review candidate
- [ ] Scenario review candidate
- [ ] Retrieval gap
- [ ] Monitor-only
- [ ] Reject / do not use

## Decision rationale

Write the reason for the selected category:

-

## Follow-up action

Select one:

- [ ] Create cache implementation issue
- [ ] Create scenario/snapshot implementation issue
- [ ] Create retrieval/query rewrite improvement issue
- [ ] Keep monitoring
- [ ] Reject and close

Follow-up issue link:
-

## Reviewer approval

- [ ] Approved for follow-up issue
- [ ] Not approved
- [ ] Needs more evidence

Reviewer notes:
-
```

---

## 4. Decision guide

Use this quick table when you are not sure which category to pick.

| Candidate pattern | Recommended category |
|---|---|
| Repeated PASS + stable official source + low fallback | Cache review candidate |
| Repeated PASS + demo/regression value + stable source | Scenario review candidate |
| Repeated WARN/NO_RESULTS + weak query terms | Retrieval gap |
| Repeated source mismatch guard trigger | Retrieval gap |
| Low count or mixed results | Monitor-only |
| Sensitive/personal content | Reject or monitor without promotion |
| Unstable/time-sensitive source | Monitor or retrieval improvement, not stable scenario |

If a candidate matches more than one pattern, prefer the **safer** category. For example, a candidate that is both "repeated PASS" and "time-sensitive" should be classified as monitor-only until the time-sensitivity is resolved.

---

## 5. Cache review checklist

Before approving a cache review candidate, verify:

- [ ] Repeated above threshold
- [ ] Most events are PASS
- [ ] Official source domain is stable
- [ ] `fallback_used` is low
- [ ] Source mismatch guard does not trigger
- [ ] Candidate reduces repeated live retrieval cost or latency
- [ ] No sensitive/personal content
- [ ] Reviewer approved follow-up issue

---

## 6. Scenario review checklist

Before approving a scenario review candidate, verify:

- [ ] Candidate has demo, smoke, regression, or safety-test value
- [ ] Expected behavior can be described clearly
- [ ] Official source domain is stable
- [ ] Pass criteria can be written without overfitting
- [ ] Candidate does not hardcode volatile facts unnecessarily
- [ ] Snapshot/scenario implementation will be reviewed separately
- [ ] Reviewer approved follow-up issue

---

## 7. Retrieval gap checklist

Before classifying as a retrieval gap, verify:

- [ ] Candidate repeats above threshold
- [ ] Results are mostly WARN/NO_RESULTS/ERROR
- [ ] Query rewrite terms appear weak or incomplete
- [ ] Source domains are absent, unstable, or off-topic
- [ ] Source mismatch guard triggers
- [ ] Candidate should not be promoted
- [ ] Follow-up should target query rewrite, search ranking, indexing, or guard tuning

---

## 8. Monitor-only checklist

Before classifying as monitor-only, verify:

- [ ] Count is below threshold
- [ ] Result quality is mixed
- [ ] Source stability is unclear
- [ ] Candidate may be temporary or event-specific
- [ ] Candidate may need more observations
- [ ] No implementation issue should be created yet

---

## 9. Example completed review — synthetic

The example below uses **synthetic** data only. Do not use real user questions or real source logs in review files.

```md
# Promotion Candidate Review

## Candidate summary

- Review date: 2026-06-07
- Reviewer: Operator
- Source report: reports/repeated-question-report.md
- Site ID: bukgu_gwangju
- Normalized key: 북구청 민원 신청 어디서 해
- Representative question: 북구청 민원 신청 어디서 해?
- Example questions:
  - 북구청 민원 신청 어디서 해?
  - 온라인 민원 어디서 해?
  - 민원 신청은 어디서 하나요?

## Frequency and status

- Total count: 8
- Time window: Synthetic example
- Answer status distribution:
  - PASS: 8
  - WARN: 0
  - NO_RESULTS: 0
  - ERROR: 0
- fallback_used count: 0
- guard_status / guard_reason: pass
- Query rewrite terms:
  - 민원
  - 민원 신청
  - 온라인 민원
  - 종합민원

## Source grounding

- Source domains:
  - bukgu.gwangju.kr
  - eminwon.bukgu.gwangju.kr
- Official source confirmed:
  - [x] Yes
  - [ ] No
  - [ ] Unclear
- Source stability:
  - [x] Stable
  - [ ] Volatile / time-sensitive
  - [ ] Unknown
- Notes on source reliability:
  - Official municipal and civil-service domains.

## Safety and privacy check

- [x] No API keys or secrets present
- [x] No Authorization headers or Bearer tokens present
- [x] No private user identifiers present
- [x] Raw question content is sanitized enough for review
- [x] Candidate does not require storing sensitive personal data

## Decision category

- [x] Cache review candidate
- [ ] Scenario review candidate
- [ ] Retrieval gap
- [ ] Monitor-only
- [ ] Reject / do not use

## Decision rationale

Repeated successful question with stable official source domains and low risk. Useful for reducing repeated retrieval cost.

## Follow-up action

- [x] Create cache implementation issue
- [ ] Create scenario/snapshot implementation issue
- [ ] Create retrieval/query rewrite improvement issue
- [ ] Keep monitoring
- [ ] Reject and close

Follow-up issue link:
- To be created

## Reviewer approval

- [x] Approved for follow-up issue
- [ ] Not approved
- [ ] Needs more evidence

Reviewer notes:
- Synthetic example only.
```

---

## 10. Non-goals

This template does **not**:

- Automatically create scenarios.
- Automatically create snapshots.
- Automatically create caches.
- Automatically create pull requests.
- Bypass human review.
- Authorize storing sensitive user data.
- Replace the scenario/cache promotion review workflow.

---

## 11. Related documents

- [Operator Question Log Guide](operator-question-log-guide.md)
- [Scenario/Cache Promotion Review Workflow](scenario-cache-promotion-review-workflow.md)
- [Repeated Question Analytics and Promotion Plan](product/repeated-question-analytics-promotion-plan.md)
- [Dynamic Retrieval and Query Learning Strategy](product/dynamic-retrieval-query-learning-strategy.md)
- `scripts/analyze_question_logs.py` — Stage 353 dry-run CLI
