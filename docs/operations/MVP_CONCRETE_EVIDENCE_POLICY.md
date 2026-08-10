# MVP Concrete Civic Evidence Policy

Status: **canonical runtime policy — #1226-A**  
Evidence policy version: **`2026-08-11.1`**  
Related canonical site-fidelity invariant: [`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md)

This policy governs concrete high-risk administrative values returned by `POST /api/mvp/ask`.

It is deliberately narrower than a general factuality checker. #1226-A covers deterministic concrete-value claims that can be matched against sanitized verified official evidence without a live network call.

## 1. Covered concrete signals

The server detects these closed signal kinds in provider answers:

- `phone`
- `url`
- `clock_time`
- `money`
- `calendar_date`

Covered examples include phone numbers, HTTP(S) URLs, explicit clock times, bounded currency amounts, and explicit calendar dates. Ordinary plain numbers are not money merely because they are numeric.

This slice does **not** semantically validate department ownership, required-document lists, eligibility/exclusions, legal effect, procedure prerequisites, application-channel meaning, or deadline semantics beyond an explicitly detected calendar date. Those remain later #1226 work.

## 2. Evidence levels are closed and fail-closed

Canonical evidence vocabulary is:

- `canonical_snapshot`
- `verified_live_source`
- `supplementary_official_citation`
- `model_only`

Verified authority is restricted to the two declared verified levels:

- `canonical_snapshot`
- `verified_live_source`

Current bounded source-state mapping:

| Runtime source state | Evidence level | Concrete-value authority |
| --- | --- | --- |
| `official_snapshot` / `canonical_snapshot` | `canonical_snapshot` | verified |
| `verified_live_source` | `verified_live_source` | verified |
| `supplementary_official_citation` | `supplementary_official_citation` | insufficient alone |
| `snapshot_unavailable` / `model_only` / `unavailable` | `model_only` | insufficient |
| unknown or undeclared level, including historical `live_official` | `model_only` | insufficient |

`live_official` is **not** a verified alias. Unknown/undeclared levels never gain authority by naming convention. An official-looking domain or provider-supplied official citation also does not promote an otherwise unverified answer.

## 3. Normalized concrete-value identity

Matching is semantic only within explicitly bounded normalization rules.

### Money

Supported currencies are:

- KRW: `KRW`, `원`, `₩`, bounded `won` form
- USD: explicit `USD` and `US$`
- EUR: `EUR`, `€`

Currency identity is part of the normalized claim. Examples:

```text
USD 50  -> money:USD:50
EUR 50  -> money:EUR:50
50 KRW  -> money:KRW:50
```

Therefore an evidence amount of `EUR 50` cannot authorize an answer of `USD 50` merely because the numeric amount is equal.

A bare `$50` is not silently interpreted as USD. It is still treated as a concrete money signal, but its currency identity is ambiguous and the answer fails closed unless a future explicit locale/currency contract defines it.

### Calendar dates

Bounded canonical forms include:

- `2026-08-20`
- `2026년 8월 20일`
- `August 20, 2026`
- non-ambiguous day-first `20/08/2026`

Equivalent forms normalize to the same actual calendar date only after calendar validity checks.

Numeric slash dates that can be interpreted both D/M/Y and M/D/Y, for example `08/09/2026`, are **detected but not guessed**. They produce an ambiguous concrete-value state and fail closed. Neither evidence for `2026-08-09` nor evidence for `2026-09-08` authorizes that ambiguous answer. Unsupported month-first slash syntax is likewise detected where bounded parsing can identify it and is not guessed into a verified date.

### Phone numbers

The detector retains Korea-local phone support and adds bounded international `+` country-code support for the current locale set:

- `+82` Korea
- `+84` Vietnam
- `+66` Thailand
- `+62` Indonesia

Spaces, hyphens, and bounded parentheses are formatting-equivalent. Ordinary long identifiers without a supported phone structure are not classified as phone numbers.

### Clock time

24-hour clock values retain `HH:MM` semantics. Supported AM/PM forms with minutes canonicalize meridiem meaning:

```text
9:00 AM  -> 09:00
9:00 PM  -> 21:00
12:00 AM -> 00:00
12:00 PM -> 12:00
```

Thus evidence `09:00` cannot authorize answer `9:00 PM`, while evidence `21:00` can. Unsupported meridiem syntax is not mis-normalized; a bounded detected unsupported form fails closed.

### URL

Normalized HTTP(S) URL identity preserves host, path, query, **and fragment**. Fragment-bearing URLs are supported only by exact normalized identity:

- evidence without fragment vs answer with fragment → mismatch
- different fragments → mismatch
- same fragment → match

This prevents an SPA/hash-routing state from inheriting authorization from another URL state.

## 4. Decision rule

The gate runs only after provider response parsing and locale validation succeed.

1. Extract normalized covered concrete values from the candidate answer.
2. If no covered concrete signal is present, allow the answer under this slice and record `no_concrete_high_risk_value`.
3. If a concrete signal is detected but its semantic interpretation is ambiguous, block with `ambiguous_concrete_value`.
4. If a concrete value is present but the evidence level is not one of the declared verified levels, block with `verified_evidence_required`.
5. For verified evidence, extract the same normalized concrete-value vocabulary from the sanitized evidence text.
6. **Every** concrete value in the candidate answer must occur with the same normalized semantic identity in verified evidence.
7. Any absent or mismatched value blocks the entire provider draft with `concrete_value_not_in_verified_evidence`.
8. If all values match, allow the answer with `all_concrete_values_verified`.

The same evidence rule applies after a locale-corrective retry.

## 5. Failure and provider-selection contract

A blocked provider draft returns:

- HTTP `200` for current v1 compatibility;
- `ok:false`;
- `failure_code:"evidence_required"`;
- `error.retryable:false`;
- a localized safe fallback in the requested locale;
- canonical source/provenance metadata when a canonical snapshot existed so the citizen can verify the current official source.

The blocked provider draft itself is never returned.

Provider-attempt telemetry records:

- `outcome:"evidence_required"`;
- `selected:false`;
- `selection_reason:"evidence_policy_rejected"`.

Evidence rejection is non-retryable and does not fall through to another provider to evade the gate. Existing locale-corrective retry ordering remains unchanged: locale correction happens before evidence assessment, and an evidence failure after that correction is final for the request.

## 6. Localized citizen fallback

The evidence-required fallback exists for the same closed five-locale set used by the MVP:

- `ko`
- `en`
- `vi`
- `th`
- `id`

The fallback tells the citizen that the specific contact/URL/time/fee/date was withheld because verified official evidence was insufficient and directs them to the displayed official source.

## 7. Operator metadata and privacy

Public/runtime metadata exposes only the evidence decision shape:

```json
{
  "evidence_policy": {
    "version": "2026-08-11.1",
    "decision": "allow | block | not_assessed",
    "evidence_level": "canonical_snapshot | verified_live_source | supplementary_official_citation | model_only",
    "signal_kinds": ["phone", "url", "clock_time", "money", "calendar_date"],
    "reason": "..."
  }
}
```

Allowed reasons are closed and include:

- `not_assessed`
- `no_concrete_high_risk_value`
- `verified_evidence_required`
- `ambiguous_concrete_value`
- `concrete_value_not_in_verified_evidence`
- `all_concrete_values_verified`

The decision object, public metadata, sanitized runtime log, and citizen fallback do **not** contain the extracted blocked phone, URL, clock time, money amount, date, or rejected provider draft.

## 8. Runtime policy-version ownership

`EVIDENCE_POLICY_VERSION` owns this detector/matching contract only.

The aggregate `/api/mvp/ask` runtime `POLICY_VERSION` is separately code-owned. It may coincidentally have the same string in some revision, but it is not an alias of `EVIDENCE_POLICY_VERSION`, and an evidence detector revision does not implicitly require an unrelated runtime-policy metadata bump.

## 9. Interaction with existing runtime policy

Order of relevant gates:

1. request byte/schema/privacy boundary;
2. runtime mode / provider availability controls;
3. canonical official context selection;
4. provider request and parse;
5. locale validation/correction;
6. **#1226 concrete evidence policy**;
7. success selection/action projection.

The deterministic server classifier remains authoritative for final action priority; the evidence policy does not allow provider output to override the deterministic action.

Canonical snapshot provenance remains authoritative. Supplementary grounding citations do not upgrade snapshot freshness or evidence level.

## 10. Offline verification contract

No live provider, Firecrawl, or official-site request is required to validate this policy.

Required regression coverage includes:

- `live_official` and unknown evidence levels do not become verified;
- canonical matching phone value → allow; hallucinated phone → block with no raw leak;
- model-only KRW/USD/EUR → block;
- same-currency exact money identity → allow; cross-currency same numeric amount → block;
- bare `$` amount → detected ambiguity and fail closed, not implicit USD;
- ISO/Korean/English-month/non-ambiguous day-first dates canonicalize to the same actual date;
- ambiguous numeric date remains a detected high-risk signal and is never authorized by guessing either interpretation;
- supported international phone formats normalize and match while ordinary long identifiers remain non-phone;
- AM/PM canonicalization preserves meridiem and 12 AM/PM edges;
- unsupported meridiem syntax does not get silently normalized;
- URL fragment mismatch blocks while an exact fragment can match;
- general guidance with no covered concrete signal → allow;
- every concrete value in a multi-value answer must be supported;
- official-domain supplementary citation alone cannot promote evidence;
- all five locale fallbacks;
- rejected provider attempt remains unselected and does not trigger provider fallback;
- runtime log exposes only signal kinds/reason, never blocked raw values;
- aggregate runtime and evidence policy versions have independent ownership.

## 11. Deferred #1226 work

Later slices must separately design and test semantic evidence requirements for claims such as:

- responsible department/office ownership;
- required documents;
- eligibility and exclusions;
- statutory or administrative deadlines without explicit detected calendar dates;
- legal effect;
- procedure prerequisites;
- application channel semantics.

Do not infer those semantic claims from this concrete-value gate, and do not mark #1226 complete based on #1226-A alone.
