# Operator Guide: Controlled Retrieval-Gap Validation

This guide covers `scripts/validate_retrieval_gaps.py` as an operator-facing workflow tool. It is intended to help teams run retrieval-gap checks without accidentally crossing provider, fetch, network, API, or Firecrawl boundaries.

## 1. Purpose

- `validate_retrieval_gaps.py` is a retrieval-gap validation CLI, not an answer-generation tool.
- Its job is to check whether official candidate sources are retrieved through the controlled pipeline.
- It is not a proof tool for exact factual absence. A negative result can mean a retrieval gap, an unsupported query, or a query that is not well aligned to the site's source structure.

## 2. CLI-only boundary

Controlled retrieval-gap validation is currently CLI-only.

Do not expose this workflow through `/api`, admin dashboard, mobile UI, or any HTTP route without a separate approved follow-up issue.

The CLI `--allow-live` flag does not mean that an HTTP request field such as `allow_live` is supported or safe to add.

Endpoint/admin/dashboard wiring is out of scope until a later approved design and implementation stage.

Default `provider=mock` and `fetch_provider=mock` behavior must remain unchanged.

No answer-generation path may be introduced. There is no supported HTTP/API `allow_live` request field. Endpoint, admin UI, and dashboard wiring remain prohibited until a separately approved follow-up stage.

## 3. When to use

Use it for:

- snapshot/demo runs that returned no results, but you suspect the site still has an official page.
- representative site questions such as mayor name, responsible officer contact, parking location, or service location.
- dry-run retrieval-gap investigation before opening a retrieval or answer follow-up issue.

Do not use it for:

- routine unit testing.
- answer generation.
- auto-promotion or source promotion.
- scenario, snapshot, or cache creation.
- broad crawling without a small human-curated question list.

## 3. Question file format

Only non-empty strings are valid.

```json
{
  "questions": [
    "구청장이 누구야?",
    "담당자 연락처 알려줘",
    "주차장이 어디있어?"
  ]
}
```

- Keep the list small and human curated.
- Do not include secrets, API keys, cookies, auth headers, or private data.

## 4. Offline validation example

```bash
python scripts/validate_retrieval_gaps.py \
  --site-id bukgu_gwangju \
  --questions-file gap_questions.json
```

- Default provider is `mock` and default fetch provider is `mock`.
- Use offline mode to check workflow, schema, guard output, and report structure.
- An offline no-result run does not prove that the real site lacks the information; it only shows that the mocked retrieval path did not return sources.

## 5. Controlled live validation example

```bash
python scripts/validate_retrieval_gaps.py \
  --site-id bukgu_gwangju \
  --questions-file gap_questions.json \
  --allow-live \
  --fetch-provider requests
```

- `--allow-live` is required for any live or non-mock provider/fetch path.
- Use explicit provider and fetch-provider selection.
- Do not use Firecrawl without a dedicated follow-up stage.
- Do not use `RUN_LIVE_*_TESTS=1`; it is unrelated to operator-controlled live validation and is forbidden for normal validation workflows.

## 6. Report interpretation

Use the report as a gap signal, not as final answer evidence.

- `source_count`: number of retrieved candidate sources included in the sanitized report.
- `guard_status`: lifecycle status such as `ok`, `blocked`, `no_results`, or error.
- `guard_reason`: short explanation for the guard status.
- `top_sources`: sanitized source metadata for inspection. Inspect `title`, `url`, `category`, and `score`.
- `query_rewrite.queries`: shows how the original question was rewritten or expanded for retrieval.

Distinguish:

- snapshot coverage limitation: the local snapshot does not contain this topic or structure.
- retrieval gap: sources likely exist on the live site, but the retrieval path did not reach them.
- no official source found: the live validation run did not find an official candidate for the requested fact type, and human judgment is needed.

## 7. Follow-up decision tree

- Official sources found but answer still fails: create an answer or source-guard follow-up issue.
- Live validation finds no sources: treat as retrieval gap or unsupported question and route to human review.
- Weak or wrong sources: open a retrieval ranking or query rewrite follow-up issue.
- Scenario, snapshot, or cache candidate is needed: open a separate human-review issue. Automatic promotion is not allowed.

## 8. Hard guardrails

- Do not execute live, network, API, or Firecrawl calls without explicit opt-in through the CLI flags above.
- Do not use API keys, secrets, cookies, or auth headers in operator workflows.
- Do not use `RUN_LIVE_*_TESTS=1`.
- Do not modify `validate_matrix()` or `evaluate_response()`.
- Do not weaken source grounding rules.
- Do not hardcode volatile facts such as mayor names, responsible officer names, phone numbers, or parking locations.
- Do not automatically create scenario, snapshot, or cache artifacts from validation output.
