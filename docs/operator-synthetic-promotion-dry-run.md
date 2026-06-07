# Operator Synthetic Promotion Dry-Run Guide

## 1. Purpose

This guide shows how an operator can run a complete repeated-question promotion review dry-run using **synthetic question logs only**.

It connects three existing pieces:

1. `docs/operator-question-log-guide.md` — how sanitized question logs are structured and analyzed.
2. `scripts/analyze_question_logs.py` — how repeated-question dry-run reports are generated.
3. `docs/promotion-candidate-review-template.md` — how a human reviewer records a promotion, retrieval-gap, monitor-only, or reject decision.

The goal is to rehearse the operator workflow without using real user logs, live network calls, provider API calls, site fetching, Firecrawl, or secrets.

This guide does **not** create scenarios, snapshots, caches, pull requests, commits, or follow-up issues automatically.

---

## 2. When to use this guide

Use this guide when you want to verify that an operator understands the promotion review workflow before reviewing real sanitized logs.

Good use cases:

- onboarding a new operator
- checking the dry-run report format
- practicing how to classify repeated questions
- testing whether the review template is understandable
- validating that retrieval gaps are not accidentally promoted
- confirming that promotion remains manual and human-reviewed

Do not use this guide as evidence that a real production question should be promoted. The examples below are synthetic only.

---

## 3. Safety rules

This dry-run must remain offline and synthetic.

Rules:

- Use only synthetic JSONL events.
- Do not paste real user logs into this document.
- Do not include API keys, tokens, cookies, session IDs, passwords, Authorization headers, IP addresses, email addresses, phone numbers, or user identifiers.
- Do not fetch live websites.
- Do not call LLM providers.
- Do not call Firecrawl.
- Do not set `RUN_LIVE_*_TESTS=1`.
- Do not create scenario, snapshot, or cache files from this dry-run.
- Do not open promotion PRs from this dry-run.
- If a candidate looks useful, create a separate follow-up issue after human review.

---

## 4. Local dry-run files

Use local paths that are not committed.

Recommended paths:

```txt
logs/synthetic-question-log.local.jsonl
reports/synthetic-repeated-question-report.md
```

These files are operator scratch files.

They should not be committed unless a future stage explicitly creates a synthetic fixture or golden report test.

---

## 5. Synthetic JSONL input

Create the local file:

```bash
mkdir -p logs reports
cat > logs/synthetic-question-log.local.jsonl <<'EOF'
{"timestamp":"2026-06-07T00:00:00Z","site_id":"bukgu_gwangju","raw_question":"북구청 민원 신청 어디서 해?","normalized_question":"북구청 민원 신청 어디서 해","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["민원","민원 신청","온라인 민원","종합민원"],"result_count":5,"source_domains":["bukgu.gwangju.kr","eminwon.bukgu.gwangju.kr"],"answer_status":"PASS","fallback_used":false,"guard_status":"pass","warnings":[]}
{"timestamp":"2026-06-07T00:01:00Z","site_id":"bukgu_gwangju","raw_question":"북구청 민원 신청 어디서 해?","normalized_question":"북구청 민원 신청 어디서 해","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["민원","민원 신청","온라인 민원","종합민원"],"result_count":4,"source_domains":["bukgu.gwangju.kr","eminwon.bukgu.gwangju.kr"],"answer_status":"PASS","fallback_used":false,"guard_status":"pass","warnings":[]}
{"timestamp":"2026-06-07T00:02:00Z","site_id":"bukgu_gwangju","raw_question":"북구청 민원 신청 어디서 해?","normalized_question":"북구청 민원 신청 어디서 해","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["민원","민원 신청","온라인 민원","종합민원"],"result_count":5,"source_domains":["bukgu.gwangju.kr","eminwon.bukgu.gwangju.kr"],"answer_status":"PASS","fallback_used":false,"guard_status":"pass","warnings":[]}
{"timestamp":"2026-06-07T00:03:00Z","site_id":"bukgu_gwangju","raw_question":"청년 일자리 공고 어디서 봐?","normalized_question":"청년 일자리 공고 어디서 봐","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["청년 일자리","일자리 공고","채용 공고","청년 지원"],"result_count":4,"source_domains":["bukgu.gwangju.kr"],"answer_status":"PASS","fallback_used":false,"guard_status":"pass","warnings":[]}
{"timestamp":"2026-06-07T00:04:00Z","site_id":"bukgu_gwangju","raw_question":"청년 일자리 공고 어디서 봐?","normalized_question":"청년 일자리 공고 어디서 봐","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["청년 일자리","일자리 공고","채용 공고","청년 지원"],"result_count":4,"source_domains":["bukgu.gwangju.kr"],"answer_status":"PASS","fallback_used":false,"guard_status":"pass","warnings":[]}
{"timestamp":"2026-06-07T00:05:00Z","site_id":"bukgu_gwangju","raw_question":"청년 일자리 공고 어디서 봐?","normalized_question":"청년 일자리 공고 어디서 봐","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["청년 일자리","일자리 공고","채용 공고","청년 지원"],"result_count":3,"source_domains":["bukgu.gwangju.kr"],"answer_status":"PASS","fallback_used":false,"guard_status":"pass","warnings":[]}
{"timestamp":"2026-06-07T00:06:00Z","site_id":"bukgu_gwangju","raw_question":"없는 지원금 신청 어디야?","normalized_question":"없는 지원금 신청 어디야","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["없는 지원금","지원금 신청"],"result_count":0,"source_domains":[],"answer_status":"NO_RESULTS","fallback_used":false,"guard_status":"no_results","warnings":["no relevant official source found"]}
{"timestamp":"2026-06-07T00:07:00Z","site_id":"bukgu_gwangju","raw_question":"없는 지원금 신청 어디야?","normalized_question":"없는 지원금 신청 어디야","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["없는 지원금","지원금 신청"],"result_count":0,"source_domains":[],"answer_status":"NO_RESULTS","fallback_used":false,"guard_status":"no_results","warnings":["no relevant official source found"]}
{"timestamp":"2026-06-07T00:08:00Z","site_id":"bukgu_gwangju","raw_question":"없는 지원금 신청 어디야?","normalized_question":"없는 지원금 신청 어디야","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["없는 지원금","지원금 신청"],"result_count":0,"source_domains":[],"answer_status":"NO_RESULTS","fallback_used":false,"guard_status":"no_results","warnings":["no relevant official source found"]}
{"timestamp":"2026-06-07T00:09:00Z","site_id":"gwangju_go_kr","raw_question":"광주시 공지사항 어디서 봐?","normalized_question":"광주시 공지사항 어디서 봐","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["공지사항","시정소식","고시공고"],"result_count":2,"source_domains":["gwangju.go.kr"],"answer_status":"WARN","fallback_used":true,"guard_status":"weak_source_match","warnings":["fallback-heavy result"]}
{"timestamp":"2026-06-07T00:10:00Z","site_id":"gwangju_go_kr","raw_question":"광주시 공지사항 어디서 봐?","normalized_question":"광주시 공지사항 어디서 봐","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["공지사항","시정소식","고시공고"],"result_count":2,"source_domains":["gwangju.go.kr"],"answer_status":"WARN","fallback_used":true,"guard_status":"weak_source_match","warnings":["fallback-heavy result"]}
{"timestamp":"2026-06-07T00:11:00Z","site_id":"gwangju_go_kr","raw_question":"광주시 공지사항 어디서 봐?","normalized_question":"광주시 공지사항 어디서 봐","provider_mode":"stub","retrieval_mode":"offline_synthetic","query_rewrite_queries":["공지사항","시정소식","고시공고"],"result_count":2,"source_domains":["gwangju.go.kr"],"answer_status":"WARN","fallback_used":true,"guard_status":"weak_source_match","warnings":["fallback-heavy result"]}
EOF
```

The sample includes four review signals:

| Synthetic group                              | Expected interpretation                |
| -------------------------------------------- | -------------------------------------- |
| Repeated `PASS` with stable official domains | cache candidate review                 |
| Repeated `PASS` with regression/demo value   | scenario candidate review              |
| Repeated `NO_RESULTS`                        | retrieval gap                          |
| Repeated `WARN` with fallback/weak guard     | monitor or retrieval improvement first |

---

## 6. Run the dry-run report

Run:

```bash
python scripts/analyze_question_logs.py \
  --input logs/synthetic-question-log.local.jsonl \
  --output reports/synthetic-repeated-question-report.md \
  --min-count 3
```

Expected behavior:

- The command reads only the local synthetic JSONL file.
- The command writes only a local Markdown report.
- The command does not fetch websites.
- The command does not call LLM providers.
- The command does not call Firecrawl.
- The command does not create scenarios, snapshots, caches, PRs, issues, or commits.

Open the report:

```bash
sed -n '1,240p' reports/synthetic-repeated-question-report.md
```

---

## 7. How to read the dry-run report

The operator should identify two broad sections:

1. Promotion candidates for human review
2. Retrieval gaps or weak results

A repeated successful question is only a **candidate**. It is not promoted automatically.

A repeated `NO_RESULTS`, `WARN`, fallback-heavy, or weak guard result should normally be treated as a retrieval problem, not as a cache or scenario candidate.

---

## 8. Copy findings into the review template

For each repeated group, copy the relevant report findings into `docs/promotion-candidate-review-template.md`.

The fields that should be filled from the report are:

| Review template field          | Source from dry-run report   |
| ------------------------------ | ---------------------------- |
| Candidate question             | normalized question group    |
| Site ID                        | `site_id`                    |
| Repeat count                   | group count                  |
| PASS / WARN / NO_RESULTS ratio | grouped answer status counts |
| Source domains                 | `source_domains`             |
| Fallback signal                | `fallback_used` rate         |
| Guard signal                   | `guard_status` values        |
| Recommended action             | analyzer recommendation      |
| Human decision                 | reviewer judgment            |

The analyzer recommendation is an input to review, not the final decision.

---

## 9. Example completed review: cache candidate

```md
## Promotion Candidate Review

### Candidate summary

- Candidate question: 북구청 민원 신청 어디서 해?
- Site ID: bukgu_gwangju
- Repeat count: 3
- Source domains: bukgu.gwangju.kr, eminwon.bukgu.gwangju.kr
- PASS / WARN / NO_RESULTS ratio: 3 / 0 / 0
- Fallback used: false
- Guard status: pass
- Analyzer recommendation: review_for_cache

### Human decision

- Decision category: cache candidate
- Decision: proceed to separate cache-review issue
- Reason: repeated successful question, stable official domains, no fallback, no guard warning
- Follow-up issue: to be created separately
```

This decision does not create a cache file. It only records that a separate cache-review issue may be opened.

---

## 10. Example completed review: scenario candidate

```md
## Promotion Candidate Review

### Candidate summary

- Candidate question: 청년 일자리 공고 어디서 봐?
- Site ID: bukgu_gwangju
- Repeat count: 3
- Source domains: bukgu.gwangju.kr
- PASS / WARN / NO_RESULTS ratio: 3 / 0 / 0
- Fallback used: false
- Guard status: pass
- Analyzer recommendation: review_for_scenario

### Human decision

- Decision category: scenario candidate
- Decision: proceed to separate scenario-review issue
- Reason: repeated successful question with likely demo/regression value
- Follow-up issue: to be created separately
```

This decision does not create a scenario fixture. It only records that a separate scenario-review issue may be opened.

---

## 11. Example completed review: retrieval gap

```md
## Promotion Candidate Review

### Candidate summary

- Candidate question: 없는 지원금 신청 어디야?
- Site ID: bukgu_gwangju
- Repeat count: 3
- Source domains: none
- PASS / WARN / NO_RESULTS ratio: 0 / 0 / 3
- Fallback used: false
- Guard status: no_results
- Analyzer recommendation: retrieval_gap

### Human decision

- Decision category: retrieval gap
- Decision: do not promote
- Reason: repeated NO_RESULTS means retrieval/query rewrite should be improved before any promotion
- Follow-up issue: separate retrieval improvement issue only if this gap appears in real sanitized logs
```

Retrieval gaps must not be converted into scenarios or caches.

---

## 12. Example completed review: monitor-only

```md
## Promotion Candidate Review

### Candidate summary

- Candidate question: 광주시 공지사항 어디서 봐?
- Site ID: gwangju_go_kr
- Repeat count: 3
- Source domains: gwangju.go.kr
- PASS / WARN / NO_RESULTS ratio: 0 / 3 / 0
- Fallback used: true
- Guard status: weak_source_match
- Analyzer recommendation: monitor

### Human decision

- Decision category: monitor-only
- Decision: do not promote
- Reason: repeated WARN and fallback-heavy result needs retrieval/source matching improvement before promotion
- Follow-up issue: none for synthetic dry-run
```

Monitor-only means the operator keeps watching the pattern. It is not a promotion decision.

---

## 13. Operator checklist

Before accepting a promotion candidate from a real report, confirm:

- [ ] The log source is sanitized.
- [ ] The candidate is based on repeated real usage, not only synthetic examples.
- [ ] The answer status is mostly `PASS`.
- [ ] Official source domains are stable.
- [ ] The result is not fallback-heavy.
- [ ] Source mismatch guard is not blocking or downgrading the result.
- [ ] The question is not too broad or ambiguous.
- [ ] The expected answer can be grounded in official sources.
- [ ] A human reviewer approved the classification.
- [ ] A separate follow-up issue will be used for any scenario/cache work.

---

## 14. Non-goals

This dry-run does not:

- store production logs
- review real user data
- create scenario fixtures
- create snapshot files
- create cache files
- create pull requests
- create follow-up issues automatically
- approve promotion automatically
- call live providers
- call Firecrawl
- fetch sites
- use API keys or secrets
- replace human review

---

## 15. Related documents

- [Operator Question Log Guide](operator-question-log-guide.md)
- [Promotion Candidate Review Template](promotion-candidate-review-template.md)
- [Scenario/Cache Promotion Review Workflow](scenario-cache-promotion-review-workflow.md)
- [Repeated-Question Analytics and Scenario-Cache Promotion Plan](product/repeated-question-analytics-promotion-plan.md)
- [Dynamic Retrieval and Query Learning Strategy](product/dynamic-retrieval-query-learning-strategy.md)
