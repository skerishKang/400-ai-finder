# Hybrid Scripted + LLM Fallback Architecture Intent

This document records the **intended product architecture** for 400-ai-finder and
distinguishes it from the **current static demo artifact**. It exists to correct
the impression that the product is permanently local/static-only or that unknown
questions are permanently bounded-demo only.

> **Docs-only intent record.** This document does **not** implement any LLM
> client, provider adapter, or live API call. It records product direction. A
> real LLM fallback still requires a separately scoped, explicitly approved issue
> plus the gates in
> [`docs/live-transition-decision-record.md`](live-transition-decision-record.md).

---

## Two tiers of the intended product

### Tier 1 — known / golden questions (deterministic scripted simulation)

- The five known resident-task questions use a **deterministic scripted /
  static simulation**.
- `source_mode: local_static` is retained; `stop_condition:
  STOP_FOR_USER_CONFIRMATION` is retained.
- This tier is stable for demo and regression testing and needs **no** live call.
- These five golden quests stay **locked** as described in
  [`docs/mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md).

### Tier 2 — unknown natural-language questions (LLM fallback intended)

- For questions that do **not** match a known golden quest, the **intended
  product behavior** is to answer via an **LLM fallback**.
- The current static Cloudflare artifact returns a bounded-demo response for
  these questions **only because of the current deployment constraint** (no LLM /
  API / network in the static build). That bounded-demo behavior is **not** the
  final product intent.
- When possible, the LLM fallback should connect the resident to a **known
  resident-task flow**.
- Where an action is needed, the intended flow uses a **Run / confirm approval**
  step that can drive a local/static action choreography today, or a future
  live-action flow once separately approved and scoped.

---

## Provider intent (DeepSeek)

- **DeepSeek is an intended provider option** and may be documented as such.
- **Never** place a real API key / secret value in docs, code, PRs, logs,
  screenshots, or fixtures.
- Use **placeholders only**:

  ```
  DEEPSEEK_API_KEY=<set outside repo>
  DEEPSEEK_BASE_URL=<provider endpoint>
  DEEPSEEK_MODEL=<model name>
  ```

- Provider selection and credential handling remain governed by
  [`docs/provider-fetch-network-boundary.md`](provider-fetch-network-boundary.md)
  and the live-transition decision record.

---

## Current static artifact vs intended product architecture

| Aspect | Current static artifact (fact) | Intended product architecture |
|--------|-------------------------------|-------------------------------|
| Known 5 questions | Deterministic local/static simulation | Same deterministic local/static simulation (unchanged) |
| Unknown questions | Bounded-demo response (no LLM in static build) | LLM fallback to answer and connect to resident-task flows |
| LLM / API / network | None in the static build (deployment constraint) | LLM fallback is a gated intended path under #862 |
| Provider | N/A in static build | DeepSeek is an intended provider option (placeholder secrets) |
| Live actions | None (STOP_FOR_USER_CONFIRMATION) | Local/static choreography now; future live action only if separately approved |

The current static artifact having **no LLM / API / network** is a true statement
about today's deployment. It must **not** be read as the final product intent.

---

## Relationship to other docs

- [`docs/live-transition-decision-record.md`](live-transition-decision-record.md) — LLM fallback is a **gated intended path**, not a prohibition.
- [`docs/mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md) — locks the five golden quests; does not fix the whole product as bounded-demo.
- [`docs/cloudflare-pages-bukgu-mvp.md`](cloudflare-pages-bukgu-mvp.md) — describes the current backend-free static artifact and its deployment constraint.
- [#862](https://github.com/skerishKang/400-ai-finder/issues/862) — official-site action navigator and live integration track; LLM fallback is part of this intended path.
