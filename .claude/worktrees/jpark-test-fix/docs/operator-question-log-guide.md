# Operator Question Log Guide

## 1. Purpose

This guide explains how operators can collect sanitized question logs and run local/offline repeated-question analytics reports.

The goal is to identify:
- repeated successful questions that may become cache/scenario review candidates
- repeated NO_RESULTS/WARN questions that indicate retrieval gaps

The guide does not enable automatic scenario, snapshot, cache, PR, or commit creation.

---

## 2. Safety principles

Operators collecting and reviewing question logs must follow these rules:

- Collect only the minimum metadata needed for product-quality analysis.
- Do not log API keys, tokens, secrets, passwords, Authorization headers, or raw environment values.
- Do not collect user identity fields (user IDs, session IDs, IP addresses, email, phone).
- Treat raw questions as potentially sensitive.
- Prefer sanitized/normalized questions for analysis and grouping.
- Use local files for operator review unless a future production storage policy is explicitly approved.
- Never paste live secrets into issue comments, PR bodies, reports, or docs.
- Never commit local log files to the repository unless they are explicitly synthetic test artifacts.

---

## 3. What gets logged

The `QuestionLogEvent` structure defines the fields that can be safely collected. Each field has a specific purpose and safety rule.

| Field | Purpose | Safety note |
|---|---|---|
| `timestamp` | When the event happened | UTC ISO timestamp |
| `site_id` | Which site/profile was queried | No user identity |
| `raw_question` | Original user question | Sanitized before storage |
| `normalized_question` | Grouping key for analytics | Preferred for repeated-question grouping |
| `provider_mode` | mock/stub/live metadata | No API key values |
| `retrieval_mode` | snapshot/live/search mode | Operational metadata only |
| `query_rewrite_queries` | Search candidates used | Query terms only, not answers |
| `result_count` | Retrieval result count | Numeric only |
| `source_domains` | Source grounding domains | Domain names only |
| `answer_status` | PASS/WARN/NO_RESULTS/ERROR-style status | Used for analytics |
| `fallback_used` | Whether fallback path was used | Quality signal |
| `guard_status` | Source mismatch guard result | Quality/safety signal |
| `warnings` | Non-sensitive warning notes | Must be sanitized |

---

## 4. What must never be logged

The following data must never be collected or written to question logs:

- API keys
- provider credentials
- Authorization headers
- Bearer tokens
- cookies
- session identifiers
- passwords
- raw environment variable dumps
- private personal identifiers (name, email, phone, address)
- full HTML/page body dumps
- stack traces containing secrets
- any value that matches a credential-like pattern (e.g. `sk-...`, `AIza...`, long random strings)

The question logger's `sanitize_text` function handles most of these redactions automatically, but operators should never add new fields that contain such values.

---

## 5. Local JSONL log file format

Question logs are stored in JSONL (JSON Lines) format: one JSON object per line.

The following are **synthetic examples** for documentation only. They do not represent real user data.

### Example 1: Successful question (potential review candidate)

```json
{"timestamp":"2026-06-07T00:00:00Z","site_id":"bukgu_gwangju","raw_question":"북구청 민원 신청 어디서 해?","normalized_question":"북구청 민원 신청 어디서 해","provider_mode":"live","retrieval_mode":"live_search","query_rewrite_queries":["민원","민원 신청","온라인 민원","종합민원"],"result_count":5,"source_domains":["bukgu.gwangju.kr","eminwon.bukgu.gwangju.kr"],"answer_status":"PASS","fallback_used":false,"guard_status":"pass","warnings":[]}
```

### Example 2: Retrieval gap (NO_RESULTS)

```json
{"timestamp":"2026-06-07T00:01:00Z","site_id":"bukgu_gwangju","raw_question":"없는 메뉴 어디야?","normalized_question":"없는 메뉴 어디야","provider_mode":"live","retrieval_mode":"live_search","query_rewrite_queries":["없는 메뉴"],"result_count":0,"source_domains":[],"answer_status":"NO_RESULTS","fallback_used":false,"guard_status":"no_results","warnings":["no relevant official source found"]}
```

### Format rules

- One JSON object per line
- Blank lines are skipped
- Invalid JSON lines will cause the dry-run CLI to fail with a line number
- Fields not listed in section 3 should not be added without review

---

## 6. Recommended local file paths

Use paths outside committed fixtures and production data.

```txt
logs/question-log.local.jsonl
reports/repeated-question-report.md
```

Notes:
- Do not commit local logs or generated reports unless they are synthetic test artifacts.
- Add local `logs/` and `reports/` directories to `.gitignore` if not already present.
- Local logs should be stored on the operator's machine, not on shared infrastructure, unless a future production storage policy is explicitly approved.

---

## 7. Running the dry-run report

Use the Stage 353 dry-run CLI to generate a review report:

```bash
python scripts/analyze_question_logs.py \
  --input logs/question-log.local.jsonl \
  --output reports/repeated-question-report.md \
  --min-count 3
```

This command is:

- **Local/offline**: Runs entirely on the operator's machine.
- **Network-free**: Does not call live providers.
- **Fetch-free**: Does not fetch sites.
- **Read-only**: Does not create scenarios, snapshots, caches, PRs, or commits.
- **Report-only**: Only writes a Markdown review report to the specified output path.

The `--min-count` flag controls the minimum repeat count to include in the report (default: 3).

The optional `--site-id` flag filters events to a single site profile.

---

## 8. Reading the report

The Markdown report contains two main sections:

### Promotion candidates for human review

- Repeated successful questions
- Stable official source domains
- Low fallback/guard issue rate

These are candidates for cache or scenario promotion **after human review**. They are not automatically promoted.

### Retrieval gaps

- Repeated NO_RESULTS/WARN questions
- Fallback-heavy questions
- Source mismatch issues

These are candidates for better query rewrite or retrieval improvements, **not** scenario promotion. They indicate product or retrieval gaps that need attention.

---

## 9. Review decisions

When reviewing a report, use the following decision guide:

| Report signal | Recommended decision |
|---|---|
| Repeated PASS, stable official source | Review for cache candidate |
| Repeated PASS, useful demo/regression value | Review for scenario candidate |
| Repeated WARN | Improve retrieval/query rewrite first |
| Repeated NO_RESULTS | Treat as retrieval gap |
| High fallback_used | Investigate source matching and query rewrite |
| Source mismatch guard triggered | Do not promote; fix retrieval/guard behavior |

The analyzer's `recommended_action` field provides an initial signal:
- `review_for_cache` — strong candidate for cache
- `review_for_scenario` — candidate for scenario (with caveats)
- `monitor` — weak signal, keep watching
- `retrieval_gap` — not a promotion candidate; needs retrieval fix

Human review remains mandatory for all decisions.

---

## 10. Human review workflow

1. Operator collects sanitized log JSONL.
2. Operator runs dry-run report.
3. Reviewer checks candidates and their source domains.
4. Reviewer verifies official source stability and answer quality.
5. Reviewer decides:
   - **monitor** — no action, keep watching
   - **improve retrieval** — fix query rewrite or retrieval before considering promotion
   - **review for cache** — add to cache candidate list for later evaluation
   - **review for scenario** — add to scenario candidate list for later evaluation
6. Only after review should a **separate** issue be created for scenario/cache promotion.

No step in this workflow creates files, PRs, or commits automatically. All promotion actions are manual and require explicit human approval.

---

## 11. Non-goals

This guide does not:

- Define production log storage.
- Enable automatic promotion of questions to scenarios or caches.
- Create snapshots.
- Create scenarios.
- Create pull requests.
- Track users.
- Authorize storing sensitive personal data.
- Replace human review.

---

## 12. Checklist before collecting logs

Before starting log collection, confirm:

- [ ] Logging purpose is product-quality analysis.
- [ ] API keys and Authorization tokens are not logged.
- [ ] User identity fields are not collected.
- [ ] Raw questions are sanitized before storage.
- [ ] Local log path is outside committed fixtures.
- [ ] Dry-run report is for human review only.
- [ ] Repeated NO_RESULTS/WARN will be treated as retrieval gaps.
- [ ] No scenario/snapshot/cache will be created automatically.
- [ ] Local log files are not committed to the repository.
- [ ] No live secrets will be pasted into issues, PRs, or docs.

---

## Related documents

- [Operator Synthetic Promotion Dry-Run Guide](operator-synthetic-promotion-dry-run.md)
- [Promotion Candidate Review Template](promotion-candidate-review-template.md)
- [Scenario/Cache Promotion Review Workflow](scenario-cache-promotion-review-workflow.md)
- [Repeated-Question Analytics and Scenario-Cache Promotion Plan](product/repeated-question-analytics-promotion-plan.md)
- [Dynamic Retrieval and Query Learning Strategy](product/dynamic-retrieval-query-learning-strategy.md)
- Stage 351: Question logging boundary
- Stage 352: Repeated-question analyzer and promotion planning
- Stage 353: Dry-run analytics CLI (`scripts/analyze_question_logs.py`)
