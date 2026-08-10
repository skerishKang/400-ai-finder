# MVP Concrete Civic Evidence Policy

Status: **canonical runtime policy — #1226-A**  
Policy version: **`2026-08-10.2`**  
Related canonical site-fidelity invariant: [`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md)

This policy governs concrete high-risk administrative values returned by `POST /api/mvp/ask`.

It is deliberately narrower than a general factuality checker. #1226-A covers deterministic concrete-value claims that can be matched exactly against sanitized verified official evidence without a live network call.

## 1. Covered concrete signals

The server currently detects these closed signal kinds in provider answers:

- `phone`
- `url`
- `clock_time`
- `money`
- `calendar_date`

Examples include a department phone number, an HTTP(S) application URL, `09:30`, a fee such as `5,000원`, and an explicit calendar date.

This first slice does **not** semantically validate department ownership, required-document lists, eligibility, legal effect, deadlines that contain no explicit date, or other free-form administrative claims. Those require later #1226 policy work.

## 2. Evidence levels

Canonical runtime evidence levels are:

- `canonical_snapshot`
- `verified_live_source`
- `supplementary_official_citation`
- `model_only`

Current legacy freshness mapping:

| Runtime source state | Evidence level | Concrete-value authority |
| --- | --- | --- |
| `official_snapshot` / `canonical_snapshot` | `canonical_snapshot` | verified |
| `verified_live_source` / `live_official` | `verified_live_source` | verified |
| `supplementary_official_citation` | `supplementary_official_citation` | insufficient alone |
| `snapshot_unavailable` / `model_only` / `unavailable` | `model_only` | insufficient |

An official-looking domain or provider-supplied official citation does not promote an otherwise unverified answer to verified evidence.

## 3. Decision rule

The gate runs only after provider response parsing and locale validation succeed.

1. Extract normalized covered concrete values from the candidate answer.
2. If no covered concrete value is present, allow the answer under this slice and record `no_concrete_high_risk_value`.
3. If a covered concrete value is present but evidence level is not verified, block the answer with `evidence_required`.
4. If evidence level is verified, extract the same normalized concrete-value vocabulary from the sanitized official evidence text.
5. **Every** concrete value found in the candidate answer must occur in that verified evidence.
6. If any value is missing, block the entire candidate answer with `evidence_required`; do not try another provider merely to evade the policy gate.
7. If all values match, allow the answer.

The same rule applies to a locale-corrective provider retry.

## 4. Failure contract

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

## 5. Localized citizen fallback

The evidence-required fallback exists for the same closed five-locale set used by the MVP:

- `ko`
- `en`
- `vi`
- `th`
- `id`

The fallback tells the citizen that the specific contact/URL/time/fee/date was withheld because verified official evidence was insufficient and directs them to the displayed official source.

## 6. Operator metadata and privacy

Public/runtime metadata exposes only the policy decision shape:

```json
{
  "evidence_policy": {
    "version": "2026-08-10.2",
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
- `concrete_value_not_in_verified_evidence`
- `all_concrete_values_verified`

The decision object, public metadata, and sanitized runtime log do **not** contain the extracted phone number, URL, time, fee, date, or rejected draft text.

## 7. Interaction with existing runtime policy

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

## 8. Offline verification contract

No live provider, Firecrawl, or official-site request is required to validate this policy.

Required regression coverage includes:

- canonical phone value present in snapshot evidence → allow;
- hallucinated phone value → block and no raw-value leak;
- model-only concrete time/URL/fee/date → block;
- general guidance with no covered concrete value → allow;
- every concrete value in a multi-value answer must be supported;
- normalized formatting equivalence for money/date values;
- official-domain supplementary citation alone cannot promote evidence;
- all five locale fallbacks;
- rejected provider attempt remains unselected;
- runtime log exposes signal kinds/reason only.

## 9. Deferred #1226 work

Later slices must separately design and test semantic evidence requirements for claims such as:

- responsible department/office ownership;
- required documents;
- eligibility and exclusions;
- statutory or administrative deadlines without explicit date values;
- legal effect;
- procedure prerequisites;
- application channel semantics.

Do not infer those semantic claims from this concrete-value gate, and do not mark #1226 complete based on #1226-A alone.
